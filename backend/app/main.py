import mimetypes
import re
import shutil
import threading
import uuid
from collections import Counter
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi import Request as HttpRequest
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from . import account, admin, catalog, daftra, daftra_sync, import_client_categories, mail, mfa, review
from .audit import Audit, changes, request_label
from .daftra import local_phone
from .database import SessionLocal, get_db, run_migrations
from .forms import (ARABIC_DIGITS, FORM_TYPES, VISIBLE_FORM_TYPES, form_fields, list_form_types, sanitize_draft,
                    validate_submission)
from .models import (Address, Attachment, AuditLog, Client, ClientCategory, Package, PackageItem, Product, Request,
                     User)
from .pages import navigation
from .config import UPLOAD_DIR, settings
from .security import (create_password_link, create_token, get_current_user, hash_password, require_page,
                       user_for_password_token, verify_password)

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
RESET_EMAIL_INTERVAL = timedelta(minutes=3)
# This many failed logins for one account within the window block further attempts until it passes
LOGIN_FAILURE_LIMIT = 8
LOGIN_FAILURE_WINDOW = timedelta(minutes=15)
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".pdf", ".mp4", ".mov", ".doc", ".docx"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    # Loading the Daftra lists takes several seconds, so start before the first user asks
    threading.Thread(target=warm_daftra_lists, daemon=True).start()
    yield


def warm_daftra_lists():
    for load in (daftra.list_staff, daftra.list_treasuries, daftra.list_order_sources):
        try:
            load()
        except daftra.DaftraError:
            pass
    # The client categories live in our database; they are copied from Daftra only the first time
    # (run app.import_client_categories to refresh them)
    with SessionLocal() as db:
        empty = db.scalar(select(func.count()).select_from(ClientCategory)) == 0
    if empty:
        try:
            import_client_categories.import_categories()
        except daftra.DaftraError:
            pass


app = FastAPI(title="FutureLife Portal", lifespan=lifespan)
app.include_router(admin.router)
app.include_router(account.router)
app.include_router(catalog.router)
app.include_router(review.router)


class LoginIn(BaseModel):
    # Email or username
    username: str
    password: str
    # The 6-digit code from the email, once the server has sent it
    code: str = ""


class ForgotIn(BaseModel):
    username: str


class SetPasswordIn(BaseModel):
    token: str
    # bcrypt reads at most 72 bytes of a password
    password: str = Field(min_length=8, max_length=72)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str | None
    full_name: str
    is_admin: bool
    # Departments and pages this user can open, in menu order
    navigation: list[dict]


def user_out(user: User) -> dict:
    return {"id": user.id, "username": user.username, "email": user.email, "full_name": user.full_name, "is_admin": user.is_admin,
            "navigation": navigation(user.pages)}


class LoginOut(BaseModel):
    # True, with no token, when the password was right and a code has been emailed
    mfa_required: bool = False
    # Where the code went, partly hidden, and how long before another can be sent
    email_hint: str | None = None
    resend_in: int | None = None
    access_token: str | None = None
    user: UserOut | None = None


class RequestIn(BaseModel):
    form_type: str
    data: dict
    action: Literal["draft", "submit"]


class RequestUpdate(BaseModel):
    data: dict
    action: Literal["draft", "submit"]


class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    field: str
    filename: str
    content_type: str
    size: int


class RequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    form_type: str
    data: dict
    status: str
    revision: int
    returned_reason: str | None
    created_at: datetime
    updated_at: datetime
    submitted_at: datetime | None
    reviewed_at: datetime | None
    attachments: list[AttachmentOut]
    daftra_invoice_no: str | None
    daftra_receipt_no: str | None
    daftra_work_order_no: str | None
    daftra_error: str | None
    daftra_synced_at: datetime | None


# ---------- Auth ----------

def find_login(identifier: str, db: Session) -> User | None:
    """The user with this email or username. Usernames never contain "@", so the two cannot clash."""
    identifier = identifier.strip().lower()
    if not identifier:
        return None
    column = User.email if "@" in identifier else User.username
    return db.scalar(select(User).where(column == identifier))


@app.post("/api/auth/login", response_model=LoginOut)
def login(body: LoginIn, db: Session = Depends(get_db), audit: Audit = Depends()):
    user = find_login(body.username, db)
    # Failures are counted under the account's username however the name was typed
    name = user.username if user else body.username.strip().lower()[:50]
    failures = db.scalar(
        select(func.count()).select_from(AuditLog).where(
            AuditLog.action == "auth.login_failed", AuditLog.username == name,
            AuditLog.at > datetime.now(timezone.utc) - LOGIN_FAILURE_WINDOW,
        )
    )
    if failures >= LOGIN_FAILURE_LIMIT:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "محاولات دخول كثيرة. حاول مرة أخرى بعد 15 دقيقة.")

    def fail(message: str, reason: str):
        audit.log(None, "auth.login_failed", username=name, after={"reason": reason})
        db.commit()
        return HTTPException(status.HTTP_401_UNAUTHORIZED, message)

    if (user is None or not user.is_active or not user.password_hash
            or not verify_password(body.password, user.password_hash)):
        raise fail("بيانات الدخول غير صحيحة", "كلمة المرور أو الحساب")
    if mfa.applies(user):
        if not user.email:
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                "حسابك يتطلب رمز تحقق بالبريد ولا يوجد له بريد إلكتروني. تواصل مع مدير النظام.")
        if not body.code.strip():
            # Asking again inside the wait keeps the code already sent
            wait = mfa.seconds_until_resend(user)
            if not wait:
                code = mfa.new_code(user)
                try:
                    mail.send_login_code(user.email, user.full_name, code, mfa.CODE_MINUTES)
                except mail.MailError:
                    raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                                        "تعذر إرسال رمز التحقق إلى بريدك الآن. حاول بعد قليل.")
                audit.log(user, "auth.mfa_code_sent")
                db.commit()
            return {"mfa_required": True, "email_hint": mfa.mask_email(user.email),
                    "resend_in": wait or mfa.RESEND_SECONDS}
        if not mfa.check_code(user, body.code):
            raise fail("رمز التحقق غير صحيح أو انتهت صلاحيته", "رمز التحقق بخطوتين")
    audit.log(user, "auth.login")
    db.commit()
    return {"access_token": create_token(user), "user": user_out(user)}


@app.post("/api/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(user: User = Depends(get_current_user), db: Session = Depends(get_db), audit: Audit = Depends()):
    audit.log(user, "auth.logout")
    db.commit()


@app.post("/api/auth/forgot-password", status_code=status.HTTP_204_NO_CONTENT)
def forgot_password(body: ForgotIn, db: Session = Depends(get_db), audit: Audit = Depends()):
    """Emails a link to set a new password. Answers the same whether or not the account exists."""
    user = find_login(body.username, db)
    sent = False
    # One email per account every few minutes, so the form cannot be used to flood an inbox
    recent = user is not None and db.scalar(
        select(AuditLog.id).where(
            AuditLog.user_id == user.id, AuditLog.action == "auth.password_reset_request",
            AuditLog.at > datetime.now(timezone.utc) - RESET_EMAIL_INTERVAL,
            AuditLog.after["email_sent"].as_boolean(),
        ).limit(1)
    )
    if user is not None and user.is_active and user.email and not recent:
        try:
            mail.send_password_link(user.email, user.full_name, user.username, create_password_link(user),
                                    settings.password_link_hours, invited=False)
            sent = True
        except mail.MailError:
            pass
    audit.log(user, "auth.password_reset_request", username=body.username.strip().lower(), after={"email_sent": sent})
    db.commit()


@app.get("/api/auth/password-link")
def check_password_link(token: str, db: Session = Depends(get_db)):
    """Tells the set-password screen whose link this is, or that it is no longer valid."""
    user = user_for_password_token(token, db)
    return {"username": user.username, "full_name": user.full_name, "invited": not user.has_password}


@app.post("/api/auth/set-password", status_code=status.HTTP_204_NO_CONTENT)
def set_password(body: SetPasswordIn, db: Session = Depends(get_db), audit: Audit = Depends()):
    user = user_for_password_token(body.token, db)
    user.password_hash = hash_password(body.password)
    audit.log(user, "auth.password_set", "user", user.id, user.username)
    db.commit()


@app.get("/api/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user_out(user)


# ---------- Requests ----------

sales_user = require_page("sales.new_request", "sales.my_requests")


def own_request(request_id: int, user: User = Depends(sales_user), db: Session = Depends(get_db)) -> Request:
    request = db.get(Request, request_id)
    if request is None or request.created_by_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "الطلب غير موجود")
    return request


def own_draft(request: Request = Depends(own_request)) -> Request:
    """A request its owner may still change: a draft, or one returned for corrections."""
    if request.status not in ("draft", "returned"):
        raise HTTPException(status.HTTP_409_CONFLICT, "الطلب مُرسل للمراجعة أو معتمد ولا يمكن تعديله")
    return request


def own_unsent_draft(request: Request = Depends(own_request)) -> Request:
    if request.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "يمكن حذف المسودات فقط")
    return request


def filled(data: dict) -> dict:
    """The answered fields only, so empty ones do not show up as changes in the audit log."""
    return {key: value for key, value in data.items() if value not in (None, "", [])}


def attachment_details(attachment: Attachment) -> dict:
    return {"field": attachment.field, "filename": attachment.filename, "size": attachment.size}


def active_products(db: Session) -> dict:
    """Our own catalog's active products, keyed by id (as a string, to match the "<field>_id" sent from the form)."""
    return {
        str(p.id): {"id": p.id, "name": p.name, "price": float(p.unit_price) if p.unit_price else 0,
                    "maintenance_group": p.maintenance_group}
        for p in db.scalars(select(Product).where(Product.is_active))
    }


def package_unit_price(item: PackageItem) -> float:
    """What one unit of a product costs inside a package, tax included and after the line's discount."""
    return round(float(catalog.line_total(item)) / item.quantity, 2)


def package_prices(db: Session) -> dict:
    """{(package id, product id): unit price}, both ids as strings like the order lines hold them."""
    return {
        (str(item.package_id), str(item.product_id)): package_unit_price(item)
        for item in db.scalars(select(PackageItem).join(Package).where(Package.is_active))
    }


def daftra_lists(form_type: str, db: Session) -> dict:
    """The Daftra lists this form's fields pick from, as {field type: {id: name}}; one that cannot
    be loaded right now is left out, and Daftra checks the id when the request is approved."""
    loaders = {"daftra_order_source": daftra.list_order_sources, "daftra_treasury": daftra.list_treasuries,
               # Our own copy, so it is always there (an empty table is treated as not loaded)
               "daftra_client_category": lambda: client_category_rows(db) or None}
    lists = {}
    for kind in {spec["type"] for spec in form_fields(form_type)} & set(loaders):
        try:
            rows = loaders[kind]()
        except daftra.DaftraError:
            continue
        if rows is not None:
            lists[kind] = {row["id"]: row["name"] for row in rows}
    return lists


def client_invoices(data: dict, db: Session) -> list[dict] | None:
    """The open invoices of the client the form names; [] when no such client is found, None when
    Daftra cannot be asked right now (the invoice is then checked when the request is approved)."""
    try:
        found = daftra_sync.existing_client_id(data, db)
        return daftra.open_invoices(found) if found is not None else []
    except daftra_sync.SyncError:
        return []
    except daftra.DaftraError:
        return None


def apply_action(request: Request, data: dict, action: str, user: User, db: Session):
    """Saves the data as a draft, or validates it and locks the request as submitted."""
    if action == "draft":
        request.data = sanitize_draft(request.form_type, data)
        return
    file_counts = Counter(a.field for a in request.attachments)
    lists = daftra_lists(request.form_type, db)
    invoices = None
    if any(spec["type"] == "daftra_client_invoice" for spec in form_fields(request.form_type)):
        invoices = client_invoices(data, db)
        if invoices is not None:
            lists["daftra_client_invoice"] = {invoice["id"]: daftra.invoice_label(invoice) for invoice in invoices}
    clean, errors = validate_submission(
        request.form_type, data, file_counts, user.full_name or user.username, active_products(db),
        package_prices(db), lists,
    )
    chosen = next((i for i in invoices or [] if i["id"] == clean.get("invoice")), None)
    if chosen and "paid_amount" not in errors and clean.get("paid_amount", 0) > chosen["unpaid"] + 0.005:
        errors["paid_amount"] = f"المبلغ أكبر من المتبقي على الفاتورة ({chosen['unpaid']:,.2f} درهم)"
    if errors:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, {"errors": errors})
    request.data = clean
    request.status = "submitted"
    request.revision += 1
    request.returned_reason = None
    request.submitted_at = datetime.now(timezone.utc)


@app.get("/api/form-types")
def form_types(user: User = Depends(sales_user)):
    return list_form_types()


def address_out(address: Address) -> dict:
    return {
        "id": address.id, "emirate": address.emirate, "area": address.area, "street": address.street,
        "house": address.house, "location_url": address.link, "is_default": address.is_default,
    }


def client_match(client: Client) -> dict:
    addresses = sorted(client.addresses, key=lambda a: a.id)
    last = addresses[-1] if addresses else None
    return {
        "daftra_id": client.daftra_id, "client_code": client.client_code, "customer_name": client.customer_name,
        "phone": client.phone, "emirate": last.emirate if last else "", "area": last.area if last else "",
        "street": last.street if last else "", "house": last.house if last else "",
        "location_url": last.link if last else "",
        "addresses": [address_out(a) for a in addresses],
    }


@app.get("/api/clients/lookup")
def lookup_client(phone: str = "", code: str = "", user: User = Depends(sales_user), db: Session = Depends(get_db)):
    """Finds a client in our own copy of Daftra's client list, by phone number or client code.

    The address filled in is the last one on file for that client; "addresses" lists all of
    them, so the sales form can offer a different one or let the user add a new one.
    """
    if phone:
        wanted = local_phone(phone)
        matches = [] if len(wanted) < 9 else db.scalars(
            select(Client).where(or_(Client.phone == wanted, Client.phone2 == wanted))
        ).all()
    else:
        digits = re.sub(r"\D", "", code.translate(ARABIC_DIGITS)).zfill(6)
        matches = [] if not digits.strip("0") else db.scalars(select(Client).where(Client.client_code == digits)).all()
    return {"matches": [client_match(c) for c in matches]}


class AddressIn(BaseModel):
    emirate: str = Field("", max_length=50)
    area: str = Field("", max_length=100)
    street: str = Field("", max_length=200)
    house: str = Field("", max_length=100)
    location_url: str = Field("", max_length=600)


@app.post("/api/clients/{daftra_id}/addresses")
def add_client_address(daftra_id: int, body: AddressIn, user: User = Depends(sales_user),
                       db: Session = Depends(get_db), audit: Audit = Depends()):
    """Adds a new address for a client already in our list, e.g. when they have moved."""
    client = db.scalar(select(Client).where(Client.daftra_id == daftra_id))
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "العميل غير موجود")
    address = Address(client_id=client.id, emirate=body.emirate.strip(), area=body.area.strip(),
                      street=body.street.strip(), house=body.house.strip(), link=body.location_url.strip())
    db.add(address)
    db.flush()
    audit.log(user, "client.address.add", "client", client.id, client.customer_name, after=address_out(address))
    db.commit()
    return address_out(address)


@app.get("/api/products")
def products_for_sales(user: User = Depends(sales_user), db: Session = Depends(get_db)):
    """Our own catalog, for the product field's search box (not Daftra's, which carries duplicate names)."""
    rows = db.scalars(select(Product).where(Product.is_active).order_by(func.lower(Product.name))).all()
    return [
        {
            "id": row.id, "name": row.name, "name_ar": row.name_ar,
            "price": float(row.unit_price) if row.unit_price else None, "description": row.description,
        }
        for row in rows
    ]


@app.get("/api/catalog/picker")
def catalog_picker(user: User = Depends(sales_user), db: Session = Depends(get_db)):
    """Packages and products for picking order lines: every active package first, then every
    active product. Picking a package is meant to add all the products inside it at once, so
    each package also lists its items with the quantity it carries in that package."""
    packages = db.scalars(select(Package).where(Package.is_active).order_by(func.lower(Package.name))).all()
    products = db.scalars(select(Product).where(Product.is_active).order_by(func.lower(Product.name))).all()
    return [
        {
            "kind": "package", "id": p.id, "name": p.name,
            "price": float(sum((catalog.line_total(item) for item in p.items), start=Decimal(0))),
            "items": [
                {"product_id": item.product_id, "name": item.product.name, "quantity": item.quantity,
                 "unit_price": package_unit_price(item)}
                for item in p.items
            ],
        }
        for p in packages
    ] + [
        {"kind": "product", "id": p.id, "name": p.name, "name_ar": p.name_ar,
         "price": float(p.unit_price) if p.unit_price else None, "maintenance_group": p.maintenance_group}
        for p in products
    ]


@app.get("/api/daftra/staff")
def daftra_staff(user: User = Depends(sales_user)):
    try:
        return daftra.list_staff()
    except daftra.DaftraError:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "تعذر تحميل الموظفين من دفترة")


@app.get("/api/daftra/treasuries")
def daftra_treasuries(user: User = Depends(sales_user)):
    try:
        return daftra.list_treasuries()
    except daftra.DaftraError:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "تعذر تحميل الخزائن من دفترة")


def client_category_rows(db: Session) -> list[dict]:
    return [
        {"id": c.id, "name": c.name, "emirate": c.emirate, "area": c.area}
        for c in db.scalars(select(ClientCategory).order_by(ClientCategory.name))
    ]


@app.get("/api/daftra/client_categories")
def daftra_client_categories(user: User = Depends(sales_user), db: Session = Depends(get_db)):
    """Our copy of Daftra's client categories, each with the الإمارة and المنطقة it fills in."""
    return client_category_rows(db)


@app.get("/api/daftra/clients/{daftra_id}")
def daftra_client(daftra_id: int, user: User = Depends(sales_user)):
    """What a form needs to know about a client from Daftra itself: their current category, and
    the invoices that still have something to pay (newest first, labelled for the drop-down)."""
    try:
        invoices = daftra.open_invoices(daftra_id)
        return {
            "category": daftra.client_category(daftra_id),
            "open_invoices": [{**invoice, "name": daftra.invoice_label(invoice)} for invoice in invoices],
        }
    except daftra.DaftraError:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "تعذر تحميل بيانات العميل من دفترة")


@app.get("/api/daftra/order_sources")
def daftra_order_sources(user: User = Depends(sales_user)):
    try:
        return daftra.list_order_sources()
    except daftra.DaftraError:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "تعذر تحميل مصادر الطلب من دفترة")


@app.get("/api/requests/mine", response_model=list[RequestOut])
def my_requests(user: User = Depends(sales_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(Request).where(Request.created_by_id == user.id).order_by(Request.updated_at.desc()).limit(200)
    ).all()


@app.post("/api/requests", response_model=RequestOut, status_code=status.HTTP_201_CREATED)
def create_request(body: RequestIn, user: User = Depends(sales_user), db: Session = Depends(get_db),
                   audit: Audit = Depends()):
    if body.form_type not in FORM_TYPES:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "نوع النموذج غير معروف")
    # A hidden form takes no new requests; ones already made with it carry on as before
    if body.form_type not in VISIBLE_FORM_TYPES:
        raise HTTPException(status.HTTP_409_CONFLICT, "هذا النموذج غير متاح حاليًا")
    request = Request(form_type=body.form_type, data={}, status="draft", revision=0, created_by_id=user.id)
    apply_action(request, body.data, body.action, user, db)
    db.add(request)
    db.flush()
    review.add_event(db, request, user, "created")
    if request.status == "submitted":
        review.add_event(db, request, user, "submitted")
    audit.log(user, "request.submit" if request.status == "submitted" else "request.create", "request",
              request.id, request_label(request), after={"form_type": request.form_type, **filled(request.data)})
    db.commit()
    return request


@app.get("/api/requests/{request_id}", response_model=RequestOut)
def get_request(request: Request = Depends(review.viewable_request)):
    return request


@app.put("/api/requests/{request_id}", response_model=RequestOut)
def update_request(body: RequestUpdate, request: Request = Depends(own_draft),
                   user: User = Depends(sales_user), db: Session = Depends(get_db), audit: Audit = Depends()):
    before = filled(request.data)
    was_returned = request.status == "returned"
    apply_action(request, body.data, body.action, user, db)
    request.updated_at = datetime.now(timezone.utc)
    old, new = changes(before, filled(request.data))
    if request.status == "submitted":
        review.add_event(db, request, user, "resubmitted" if was_returned else "submitted")
        audit.log(user, "request.submit", "request", request.id, request_label(request), old, new)
    elif old or new:
        audit.log(user, "request.update", "request", request.id, request_label(request), old, new)
    db.commit()
    return request


@app.delete("/api/requests/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_draft(request: Request = Depends(own_unsent_draft), user: User = Depends(sales_user),
                 db: Session = Depends(get_db), audit: Audit = Depends()):
    audit.log(user, "request.delete", "request", request.id, request_label(request),
              before={"form_type": request.form_type, **filled(request.data)})
    db.delete(request)
    db.commit()
    shutil.rmtree(UPLOAD_DIR / str(request.id), ignore_errors=True)


# ---------- Attachments ----------

@app.post("/api/requests/{request_id}/attachments", response_model=AttachmentOut,
          status_code=status.HTTP_201_CREATED)
async def upload_attachment(field: str, filename: str, http_request: HttpRequest,
                            request: Request = Depends(own_draft), user: User = Depends(sales_user),
                            db: Session = Depends(get_db), audit: Audit = Depends()):
    """The file is sent as the raw request body; field and filename come in the query string."""
    file_fields = {spec["name"] for spec in form_fields(request.form_type) if spec["type"] == "files"}
    if field not in file_fields:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "حقل المرفق غير معروف")
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "نوع الملف غير مسموح (صور، PDF، فيديو أو Word فقط)")
    too_large = HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "حجم الملف أكبر من 20 ميجابايت")
    if int(http_request.headers.get("content-length") or 0) > MAX_UPLOAD_BYTES:
        raise too_large
    content = await http_request.body()
    if not content:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "الملف فارغ")
    if len(content) > MAX_UPLOAD_BYTES:
        raise too_large

    folder = UPLOAD_DIR / str(request.id)
    folder.mkdir(parents=True, exist_ok=True)
    stored_name = uuid.uuid4().hex + extension
    (folder / stored_name).write_bytes(content)
    attachment = Attachment(
        request_id=request.id, field=field, filename=Path(filename).name[:255], stored_name=stored_name,
        content_type=mimetypes.guess_type(filename)[0] or "application/octet-stream", size=len(content),
    )
    db.add(attachment)
    db.flush()
    audit.log(user, "attachment.upload", "attachment", attachment.id, request_label(request),
              after=attachment_details(attachment))
    db.commit()
    return attachment


def own_attachment(attachment_id: int, user: User = Depends(sales_user), db: Session = Depends(get_db)) -> Attachment:
    attachment = db.get(Attachment, attachment_id)
    if attachment is None or attachment.request.created_by_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "المرفق غير موجود")
    return attachment


def viewable_attachment(attachment_id: int, user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)) -> Attachment:
    attachment = db.get(Attachment, attachment_id)
    if attachment is None or not review.can_view(attachment.request, user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "المرفق غير موجود")
    return attachment


@app.get("/api/attachments/{attachment_id}")
def download_attachment(attachment: Attachment = Depends(viewable_attachment), user: User = Depends(get_current_user),
                        db: Session = Depends(get_db), audit: Audit = Depends()):
    path = UPLOAD_DIR / str(attachment.request_id) / attachment.stored_name
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "المرفق غير موجود")
    audit.log(user, "attachment.download", "attachment", attachment.id, request_label(attachment.request),
              after={"filename": attachment.filename})
    db.commit()
    return FileResponse(path, media_type=attachment.content_type, filename=attachment.filename,
                        content_disposition_type="inline")


@app.delete("/api/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attachment(attachment: Attachment = Depends(own_attachment), user: User = Depends(sales_user),
                      db: Session = Depends(get_db), audit: Audit = Depends()):
    if attachment.request.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "تم إرسال الطلب ولا يمكن تعديله")
    audit.log(user, "attachment.delete", "attachment", attachment.id, request_label(attachment.request),
              before=attachment_details(attachment))
    db.delete(attachment)
    db.commit()
    (UPLOAD_DIR / str(attachment.request_id) / attachment.stored_name).unlink(missing_ok=True)
