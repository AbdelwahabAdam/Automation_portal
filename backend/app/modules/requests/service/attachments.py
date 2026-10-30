"""The files on a request: uploading, opening and removing one."""

import mimetypes
from pathlib import Path

from sqlalchemy.orm import Session

from ....core.config import UPLOAD_DIR
from ....core.context import Actor
from ....core.errors import BadRequest, Conflict, NotFound
from ... import form_engine
from ...audit import log as audit_log
from .. import repo
from ..labels import request_label
from ..models import Attachment, Request
from . import access

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".pdf", ".mp4", ".mov", ".doc", ".docx"}
TOO_LARGE = "حجم الملف أكبر من 20 ميجابايت"


class TooLarge(Conflict):
    """The file is over the limit: 413, as before."""

    status_code = 413


def details(attachment: Attachment) -> dict:
    return {"field": attachment.field, "filename": attachment.filename, "size": attachment.size}


def file_fields(form_type: str) -> set[str]:
    """The form's upload fields; the PDFs approving a request saves are not among them."""
    return {spec["name"] for spec in form_engine.form_fields(form_type) if spec["type"] == "files"}


def plain_filename(filename: str) -> str:
    """The file's own name, without any folder a browser sent with it (C:\\Users\\…\\photo.jpg)."""
    return Path(filename.replace("\\", "/")).name[:255]


def check_upload(request: Request, field: str, filename: str, declared_length: int) -> str:
    """What can be checked before the body is read. Returns the file's own name."""
    if field not in file_fields(request.form_type):
        raise BadRequest("حقل المرفق غير معروف")
    name = plain_filename(filename)
    if Path(name).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise BadRequest("نوع الملف غير مسموح (صور، PDF، فيديو أو Word فقط)")
    if declared_length > MAX_UPLOAD_BYTES:
        raise TooLarge(TOO_LARGE)
    return name


def store(db: Session, who: Actor, request: Request, field: str, name: str, content: bytes) -> Attachment:
    if not content:
        raise BadRequest("الملف فارغ")
    if len(content) > MAX_UPLOAD_BYTES:
        raise TooLarge(TOO_LARGE)
    attachment = repo.save_file(
        db, request, field, name, content,
        content_type=mimetypes.guess_type(name)[0] or "application/octet-stream",
    )
    db.flush()
    audit_log(db, who, "attachment.upload", "attachment", attachment.id, request_label(request),
              after=details(attachment))
    db.commit()
    return attachment


def path_of(attachment: Attachment) -> Path:
    path = UPLOAD_DIR / str(attachment.request_id) / attachment.stored_name
    if not path.exists():
        raise NotFound("المرفق غير موجود")
    return path


def record_download(db: Session, who: Actor, attachment: Attachment):
    audit_log(db, who, "attachment.download", "attachment", attachment.id,
              request_label(attachment.request), after={"filename": attachment.filename})
    db.commit()


def delete(db: Session, who: Actor, attachment: Attachment):
    # Files can be added while the request is a draft or returned for corrections, so they can be removed then too
    if attachment.request.status not in access.EDITABLE:
        raise Conflict("تم إرسال الطلب ولا يمكن تعديله")
    # The PDFs Daftra's documents were saved as stay with the request
    if attachment.field not in file_fields(attachment.request.form_type):
        raise Conflict("هذا الملف أنشأته البوابة عند الاعتماد ولا يمكن حذفه")
    audit_log(db, who, "attachment.delete", "attachment", attachment.id,
              request_label(attachment.request), before=details(attachment))
    stored = UPLOAD_DIR / str(attachment.request_id) / attachment.stored_name
    db.delete(attachment)
    db.commit()
    stored.unlink(missing_ok=True)
