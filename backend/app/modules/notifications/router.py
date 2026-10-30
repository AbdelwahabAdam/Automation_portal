"""The mail test page: which emails there are, how one looks, and sending one to check the settings."""

import re

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.database import get_db
from ...core.errors import ExternalFailure, Invalid, NotFound
from ...core.security import require
from ..audit import Audit
from . import service
from .schemas import MailTestIn

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_EMAIL = 254

may_test = require("admin.mail")
router = APIRouter(prefix="/api/admin", dependencies=[Depends(may_test)])


def known_email(name: str) -> str:
    if name not in service.EMAILS:
        raise NotFound("قالب البريد غير معروف")
    return name


@router.get("/mail")
def mail_settings(admin=Depends(may_test)):
    """The emails that can be tested and where they are sent from. The password is never included."""
    return {
        "templates": [{"key": key, "label": email["label"]} for key, email in service.EMAILS.items()],
        "configured": service.is_configured(),
        "server": f"{settings.smtp_host}:{settings.smtp_port}" if settings.smtp_host else "",
        "sender": settings.mail_from,
        "default_to": admin.email or "",
    }


@router.get("/mail/preview/{name}")
def preview_mail(name: str = Depends(known_email), admin=Depends(may_test)):
    subject, _, html = service.compose_sample(name, admin.email or "name@example.com",
                                              admin.full_name or admin.username)
    return {"subject": subject, "html": html}


@router.post("/mail/test", status_code=status.HTTP_204_NO_CONTENT)
def send_test_mail(body: MailTestIn, admin=Depends(may_test), db: Session = Depends(get_db),
                   audit: Audit = Depends()):
    """Sends one email with made-up values, to check the mail settings and how a template looks in an inbox."""
    name = known_email(body.template)
    to = body.to.strip().lower()
    if len(to) > MAX_EMAIL or not EMAIL_RE.match(to):
        raise Invalid("اكتب بريدًا إلكترونيًا صحيحًا")
    error = None
    try:
        service.send(to, *service.compose_sample(name, to, admin.full_name or admin.username))
    except service.MailError as failure:
        error = str(failure)
    audit.log(admin, "mail.test", after={"template": name, "email": to, "email_sent": error is None})
    db.commit()
    if error:
        # The mail server's own words, since this page exists to diagnose the mail settings
        raise ExternalFailure(f"تعذر الإرسال. رد خادم البريد: {error}")
