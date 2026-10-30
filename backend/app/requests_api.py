"""A salesperson's requests: drafts, submitting for review, and the files attached to them."""

import mimetypes
import shutil
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi import Request as HttpRequest
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from . import catalog, daftra, daftra_sync, review
from .audit import Audit, changes, request_label
from .config import UPLOAD_DIR
from .database import get_db
from .forms import FORM_TYPES, VISIBLE_FORM_TYPES, form_fields, list_form_types, sanitize_draft, validate_submission
from .lookups import client_category_rows
from .models import Attachment, Package, PackageItem, Product, Request, User
from .security import get_current_user, sales_user

router = APIRouter(prefix="/api")

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".pdf", ".mp4", ".mov", ".doc", ".docx"}
# A request its owner may still change: a draft, or one returned for corrections
EDITABLE = ("draft", "returned")


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


# ---------- Who may touch a request ----------

def own_request(request_id: int, user: User = Depends(sales_user), db: Session = Depends(get_db)) -> Request:
    request = db.get(Request, request_id)
    if request is None or request.created_by_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "الطلب غير موجود")
    return request


def own_draft(request: Request = Depends(own_request)) -> Request:
    """A request its owner may still change: a draft, or one returned for corrections."""
    if request.status not in EDITABLE:
        raise HTTPException(status.HTTP_409_CONFLICT, "الطلب مُرسل للمراجعة أو معتمد ولا يمكن تعديله")
    return request


def own_unsent_draft(request: Request = Depends(own_request)) -> Request:
    if request.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "يمكن حذف المسودات فقط")
    return request


# ---------- Saving and submitting ----------

def filled(data: dict) -> dict:
    """The answered fields only, so empty ones do not show up as changes in the audit log."""
    return {key: value for key, value in data.items() if value not in (None, "", [])}


def active_products(db: Session) -> dict:
    """Our own catalog's active products, keyed by id (as a string, to match the "<field>_id" sent from the form)."""
    return {
        str(p.id): {"id": p.id, "name": p.name, "price": float(p.unit_price) if p.unit_price else 0,
                    "maintenance_group": p.maintenance_group, "daftra_id": p.daftra_id}
        for p in db.scalars(select(Product).where(Product.is_active))
    }


def package_prices(db: Session) -> dict:
    """{(package id, product id): unit price}, both ids as strings like the order lines hold them."""
    items = db.scalars(select(PackageItem).join(Package).where(Package.is_active).options(selectinload(PackageItem.product)))
    return {(str(item.package_id), str(item.product_id)): catalog.unit_price_in_package(item) for item in items}


def daftra_lists(form_type: str, db: Session) -> dict:
    """The Daftra lists this form's fields pick from, as {field type: {id: name}}; one that cannot
    be loaded right now is left out, and Daftra checks the id when the request is approved."""
    loaders = {"daftra_order_source": daftra.list_order_sources, "daftra_treasury": daftra.list_treasuries,
               "daftra_staff": daftra.list_staff_members,
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
        package_prices(db), lists, new_client=not daftra_sync.known_client(data, db),
    )
    chosen = next((i for i in invoices or [] if i["id"] == clean.get("invoice")), None)
    if chosen and "paid_amount" not in errors and clean.get("paid_amount", 0) > chosen["unpaid"] + 0.005:
        errors["paid_amount"] = f"المبلغ أكبر من المتبقي على الفاتورة ({chosen['unpaid']:,.2f} درهم)"
    if errors:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, {"errors": errors})
    request.data = clean
    request.status = "submitted"
    request.revision += 1
    request.returned_reason = None
    request.submitted_at = datetime.now(timezone.utc)


@router.get("/form-types")
def form_types(user: User = Depends(sales_user)):
    return list_form_types()


@router.get("/requests/mine", response_model=list[RequestOut])
def my_requests(user: User = Depends(sales_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(Request).where(Request.created_by_id == user.id).options(selectinload(Request.attachments))
        .order_by(Request.updated_at.desc()).limit(200)
    ).all()


@router.get("/requests/mine/counts")
def my_request_counts(user: User = Depends(sales_user), db: Session = Depends(get_db)):
    """How many of the user's requests are in each status, e.g. for «المسودات 3» on the forms page."""
    rows = db.execute(select(Request.status, func.count()).where(Request.created_by_id == user.id).group_by(Request.status))
    return {"draft": 0, "submitted": 0, "returned": 0, "approved": 0, **dict(rows.all())}


@router.post("/requests", response_model=RequestOut, status_code=status.HTTP_201_CREATED)
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


@router.get("/requests/{request_id}", response_model=RequestOut)
def get_request(request: Request = Depends(review.viewable_request)):
    return request


@router.put("/requests/{request_id}", response_model=RequestOut)
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


@router.delete("/requests/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_draft(request: Request = Depends(own_unsent_draft), user: User = Depends(sales_user),
                 db: Session = Depends(get_db), audit: Audit = Depends()):
    audit.log(user, "request.delete", "request", request.id, request_label(request),
              before={"form_type": request.form_type, **filled(request.data)})
    db.delete(request)
    db.commit()
    shutil.rmtree(UPLOAD_DIR / str(request.id), ignore_errors=True)


# ---------- Attachments ----------

def attachment_details(attachment: Attachment) -> dict:
    return {"field": attachment.field, "filename": attachment.filename, "size": attachment.size}


def file_fields(form_type: str) -> set[str]:
    """The form's upload fields; the PDFs approving a request saves are not among them."""
    return {spec["name"] for spec in form_fields(form_type) if spec["type"] == "files"}


def plain_filename(filename: str) -> str:
    """The file's own name, without any folder a browser sent with it (C:\\Users\\…\\photo.jpg)."""
    return Path(filename.replace("\\", "/")).name[:255]


@router.post("/requests/{request_id}/attachments", response_model=AttachmentOut,
             status_code=status.HTTP_201_CREATED)
async def upload_attachment(field: str, filename: str, http_request: HttpRequest,
                            request: Request = Depends(own_draft), user: User = Depends(sales_user),
                            db: Session = Depends(get_db), audit: Audit = Depends()):
    """The file is sent as the raw request body; field and filename come in the query string."""
    if field not in file_fields(request.form_type):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "حقل المرفق غير معروف")
    name = plain_filename(filename)
    extension = Path(name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "نوع الملف غير مسموح (صور، PDF، فيديو أو Word فقط)")
    too_large = HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "حجم الملف أكبر من 20 ميجابايت")
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
        request_id=request.id, field=field, filename=name, stored_name=stored_name,
        content_type=mimetypes.guess_type(name)[0] or "application/octet-stream", size=len(content),
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


@router.get("/attachments/{attachment_id}")
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


@router.delete("/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attachment(attachment: Attachment = Depends(own_attachment), user: User = Depends(sales_user),
                      db: Session = Depends(get_db), audit: Audit = Depends()):
    # Files can be added while the request is a draft or returned for corrections, so they can be removed then too
    if attachment.request.status not in EDITABLE:
        raise HTTPException(status.HTTP_409_CONFLICT, "تم إرسال الطلب ولا يمكن تعديله")
    # The PDFs Daftra's documents were saved as stay with the request
    if attachment.field not in file_fields(attachment.request.form_type):
        raise HTTPException(status.HTTP_409_CONFLICT, "هذا الملف أنشأته البوابة عند الاعتماد ولا يمكن حذفه")
    audit.log(user, "attachment.delete", "attachment", attachment.id, request_label(attachment.request),
              before=attachment_details(attachment))
    db.delete(attachment)
    db.commit()
    (UPLOAD_DIR / str(attachment.request_id) / attachment.stored_name).unlink(missing_ok=True)
