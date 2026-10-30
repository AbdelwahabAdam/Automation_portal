"""The files on a request. Transport only."""

from fastapi import APIRouter, Depends, status
from fastapi import Request as HttpRequest
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ....core.context import Actor
from ....core.database import get_db
from ....core.security import acting, get_current_user
from .. import schemas
from ..models import Attachment, Request
from ..service import access
from ..service import attachments as service

router = APIRouter(prefix="/api")


def own_draft(request_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)) -> Request:
    return access.own_draft(db, request_id, user)


def own_attachment(attachment_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)) -> Attachment:
    return access.own_attachment(db, attachment_id, user)


def viewable_attachment(attachment_id: int, user=Depends(get_current_user),
                        db: Session = Depends(get_db)) -> Attachment:
    return access.viewable_attachment(db, attachment_id, user)


@router.post("/requests/{request_id}/attachments", response_model=schemas.AttachmentOut,
             status_code=status.HTTP_201_CREATED)
async def upload_attachment(field: str, filename: str, http_request: HttpRequest,
                            request: Request = Depends(own_draft),
                            who: Actor = Depends(acting(get_current_user)), db: Session = Depends(get_db)):
    """The file is sent as the raw request body; field and filename come in the query string."""
    name = service.check_upload(request, field, filename,
                                int(http_request.headers.get("content-length") or 0))
    content = await http_request.body()
    return service.store(db, who, request, field, name, content)


@router.get("/attachments/{attachment_id}")
def download_attachment(attachment: Attachment = Depends(viewable_attachment),
                        who: Actor = Depends(acting(get_current_user)), db: Session = Depends(get_db)):
    path = service.path_of(attachment)
    service.record_download(db, who, attachment)
    return FileResponse(path, media_type=attachment.content_type, filename=attachment.filename,
                        content_disposition_type="inline")


@router.delete("/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attachment(attachment: Attachment = Depends(own_attachment),
                      who: Actor = Depends(acting(get_current_user)), db: Session = Depends(get_db)):
    service.delete(db, who, attachment)
