"""The files on a request. Transport only."""

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi import Request as HttpRequest
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ....core.context import Actor
from ....core.database import get_db
from ....core.security import acting, create_link_token, get_current_user, user_for_link_token
from .. import schemas
from ..models import Attachment, Request
from ..service import access
from ..service import attachments as service

router = APIRouter(prefix="/api")

# A file opened in a tab of its own: the browser fetches it without the login header, so the link
# carries a token good for that one file. An hour, so the viewer can still reload or save it.
FILE_LINK = "file"
FILE_LINK_MINUTES = 60
LINK_EXPIRED = "انتهت صلاحية رابط الملف. افتحه من البوابة مرة أخرى."


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


def send_file(db: Session, who: Actor, attachment: Attachment) -> FileResponse:
    path = service.path_of(attachment)
    service.record_download(db, who, attachment)
    return FileResponse(path, media_type=attachment.content_type, filename=attachment.filename,
                        content_disposition_type="inline")


@router.get("/attachments/{attachment_id}")
def download_attachment(attachment: Attachment = Depends(viewable_attachment),
                        who: Actor = Depends(acting(get_current_user)), db: Session = Depends(get_db)):
    return send_file(db, who, attachment)


@router.post("/attachments/{attachment_id}/link")
def attachment_link(attachment: Attachment = Depends(viewable_attachment), user=Depends(get_current_user)):
    """An address the browser opens the file at itself. Opened from a blob instead, the browser's
    viewer saves it under a random id; here it is saved under the name the portal shows."""
    token = create_link_token(user, FILE_LINK, FILE_LINK_MINUTES, att=attachment.id)
    return {"url": f"/api/files/{attachment.id}/{quote(attachment.filename, safe='')}?token={token}"}


@router.get("/files/{attachment_id}/{filename}")
def open_file(attachment_id: int, filename: str, token: str, http_request: HttpRequest,
              db: Session = Depends(get_db)):
    """The file behind a link from attachment_link. The name in the path is only for the browser;
    who may see the file is checked again, so a link stops working once its user loses access."""
    user = user_for_link_token(db, token, FILE_LINK, att=attachment_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, LINK_EXPIRED)
    attachment = access.viewable_attachment(db, attachment_id, user)
    return send_file(db, Actor.of(user, http_request), attachment)


@router.delete("/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attachment(attachment: Attachment = Depends(own_attachment),
                      who: Actor = Depends(acting(get_current_user)), db: Session = Depends(get_db)):
    service.delete(db, who, attachment)
