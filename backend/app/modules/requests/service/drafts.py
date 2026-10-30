"""Saving a request as a draft, and submitting it for review."""

from collections import Counter
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ....core.context import Actor
from ....core.errors import Conflict, Invalid, NotFound, SyncError
from ....integrations import daftra
from ... import catalog, clients, form_engine
from ...audit import changes
from ...audit import log as audit_log
from .. import repo
from ..labels import request_label
from ..models import Request
from . import access, review


def filled(data: dict) -> dict:
    """The answered fields only, so empty ones do not show up as changes in the audit log."""
    return {key: value for key, value in data.items() if value not in (None, "", [])}


def daftra_lists(form_type: str, db: Session) -> dict:
    """The Daftra lists this form's fields pick from, as {field type: {id: name}}; one that cannot
    be loaded right now is left out, and Daftra checks the id when the request is approved."""
    loaders = {"daftra_order_source": daftra.list_order_sources, "daftra_treasury": daftra.list_treasuries,
               "daftra_staff": daftra.list_staff_members,
               # Our own copy, so it is always there (an empty table is treated as not loaded)
               "daftra_client_category": lambda: clients.categories(db) or None}
    lists = {}
    for kind in {spec["type"] for spec in form_engine.form_fields(form_type)} & set(loaders):
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
        found = clients.existing_client_id(data, db)
        return clients.open_invoices(found) if found is not None else []
    except SyncError:
        return []
    except daftra.DaftraError:
        return None


def apply_action(db: Session, request: Request, data: dict, action: str, user):
    """Saves the data as a draft, or validates it and locks the request as submitted."""
    if action == "draft":
        request.data = form_engine.sanitize_draft(request.form_type, data)
        return
    file_counts = Counter(a.field for a in request.attachments)
    lists = daftra_lists(request.form_type, db)
    invoices = None
    if any(spec["type"] == "daftra_client_invoice" for spec in form_engine.form_fields(request.form_type)):
        invoices = client_invoices(data, db)
        if invoices is not None:
            lists["daftra_client_invoice"] = {invoice["id"]: clients.invoice_label(invoice) for invoice in invoices}
    clean, errors = form_engine.validate_submission(
        request.form_type, data, file_counts, user.full_name or user.username,
        catalog.active_products_for_forms(db), catalog.package_prices(db), lists,
        new_client=not clients.known_client(data, db),
    )
    # Then whatever this form checks that the field rules cannot express
    spec = form_engine.get(request.form_type)
    if spec.validate:
        choices = {**lists, "daftra_client_invoice": invoices or []}
        for field, message in spec.validate(
            clean, form_engine.CheckContext(db=db, user=user, choices=choices)
        ).items():
            errors.setdefault(field, message)
    if errors:
        raise Invalid(fields=errors)
    request.data = clean
    request.status = "submitted"
    request.revision += 1
    request.returned_reason = None
    request.submitted_at = datetime.now(timezone.utc)


def create(db: Session, who: Actor, form_type: str, data: dict, action: str) -> Request:
    user = who.user
    if not form_engine.known(form_type):
        raise NotFound("نوع النموذج غير معروف")
    # This very form, not forms in general: a technician cannot open new_sale by API
    access.check_may_submit(user, form_type)
    # A hidden form takes no new requests; ones already made with it carry on as before
    if not form_engine.get(form_type).visible:
        raise Conflict("هذا النموذج غير متاح حاليًا")
    request = Request(form_type=form_type, data={}, status="draft", revision=0, created_by_id=user.id)
    apply_action(db, request, data, action, user)
    db.add(request)
    db.flush()
    review.add_event(db, request, user, "created")
    if request.status == "submitted":
        review.add_event(db, request, user, "submitted")
    audit_log(db, who, "request.submit" if request.status == "submitted" else "request.create", "request",
              request.id, request_label(request),
              after={"form_type": request.form_type, **filled(request.data)})
    db.commit()
    return request


def update(db: Session, who: Actor, request: Request, data: dict, action: str) -> Request:
    user = who.user
    before = filled(request.data)
    was_returned = request.status == "returned"
    apply_action(db, request, data, action, user)
    request.updated_at = datetime.now(timezone.utc)
    old, new = changes(before, filled(request.data))
    if request.status == "submitted":
        review.add_event(db, request, user, "resubmitted" if was_returned else "submitted")
        audit_log(db, who, "request.submit", "request", request.id, request_label(request), old, new)
    elif old or new:
        audit_log(db, who, "request.update", "request", request.id, request_label(request), old, new)
    db.commit()
    return request


def delete(db: Session, who: Actor, request: Request):
    audit_log(db, who, "request.delete", "request", request.id, request_label(request),
              before={"form_type": request.form_type, **filled(request.data)})
    request_id = request.id
    db.delete(request)
    db.commit()
    repo.remove_folder(request_id)


def mine(db: Session, user) -> list[Request]:
    return repo.by_owner(db, user.id)


def my_counts(db: Session, user) -> dict:
    """How many of the user's requests are in each status, e.g. for «المسودات 3» on the forms page."""
    return {"draft": 0, "submitted": 0, "returned": 0, "approved": 0, **repo.counts_by_status(db, user.id)}
