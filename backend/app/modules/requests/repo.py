"""The queries on requests' own tables. No commits, no decisions."""

import shutil
import uuid
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ...core.config import UPLOAD_DIR
from .models import Attachment, Request


def count_by_owner(db: Session, user_id: int) -> int:
    """How many requests this user has made. A user with any is stopped, not deleted."""
    return db.scalar(select(func.count()).select_from(Request).where(Request.created_by_id == user_id))


def by_owner(db: Session, user_id: int, limit: int = 200) -> list[Request]:
    return list(db.scalars(
        select(Request).where(Request.created_by_id == user_id)
        .options(selectinload(Request.attachments), selectinload(Request.documents))
        .order_by(Request.updated_at.desc()).limit(limit)
    ))


def counts_by_status(db: Session, user_id: int) -> dict:
    rows = db.execute(
        select(Request.status, func.count()).where(Request.created_by_id == user_id).group_by(Request.status)
    )
    return dict(rows.all())


def queue(db: Session, form_types: list[str], limit: int = 1000) -> list[Request]:
    """The requests of these forms, newest first: those sent, and the employees' drafts, a draft
    by when it was last saved. Only the forms the reviewer may see are asked for."""
    if not form_types:
        return []
    return list(db.scalars(
        select(Request).where(Request.form_type.in_(form_types))
        .options(selectinload(Request.created_by), selectinload(Request.reviewed_by),
                 selectinload(Request.documents))
        .order_by(func.coalesce(Request.submitted_at, Request.updated_at).desc()).limit(limit)
    ))


def lock(db: Session, request_id: int):
    """Held until the commit, so two managers approving at once cannot both create the documents."""
    db.execute(select(Request.id).where(Request.id == request_id).with_for_update())
    return db.get(Request, request_id)


def remove_folder(request_id: int):
    shutil.rmtree(UPLOAD_DIR / str(request_id), ignore_errors=True)


def save_file(db: Session, request, field: str, filename: str, content: bytes,
              content_type: str = "application/pdf") -> Attachment:
    """Puts a file in the request's folder and records it as one of its attachments.

    `invoicing` draws the invoice, receipt and work-order PDFs and names them; the attachments
    table is this module's, so the saving happens here.
    """
    folder = UPLOAD_DIR / str(request.id)
    folder.mkdir(parents=True, exist_ok=True)
    stored_name = uuid.uuid4().hex + Path(filename).suffix.lower()
    (folder / stored_name).write_bytes(content)
    attachment = Attachment(request=request, field=field, filename=filename[:255],
                            stored_name=stored_name, content_type=content_type, size=len(content))
    db.add(attachment)
    return attachment
