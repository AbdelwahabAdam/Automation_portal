"""Sending email through the SMTP server set in .env.

Each email is a pair of Jinja2 templates in `templates/email`: <name>.html, which extends
base.html for the shared look, and <name>.txt for mail apps that show plain text.
"""

import smtplib
from email.message import EmailMessage
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from ...core.config import settings

TIMEOUT_SECONDS = 15
IMPLICIT_TLS_PORT = 465
PORTAL_NAME = "بوابة المستقبل لايف"

templates = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates" / "email"),
    autoescape=select_autoescape(["html"]),
    # A value missing from a template is an error, not a silent blank in someone's inbox
    undefined=StrictUndefined,
)


def render(name: str, **values) -> tuple[str, str]:
    """The plain-text and HTML bodies of one email."""
    values = {"portal_name": PORTAL_NAME, **values}
    text = templates.get_template(f"{name}.txt").render(values).strip() + "\n"
    return text, templates.get_template(f"{name}.html").render(values)


class MailError(Exception):
    pass


def is_configured() -> bool:
    return bool(settings.smtp_host and settings.mail_from)


def connect() -> smtplib.SMTP:
    """Port 465 is encrypted from the first byte; other ports start plain and upgrade when smtp_starttls is on."""
    if settings.smtp_port == IMPLICIT_TLS_PORT:
        return smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=TIMEOUT_SECONDS)
    server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=TIMEOUT_SECONDS)
    if settings.smtp_starttls:
        server.starttls()
    return server


def send(to: str, subject: str, text: str, html: str, attachments: list[tuple[str, bytes, str]] = ()):
    """attachments: (filename, content, MIME type) each, e.g. an invoice's PDF."""
    if not is_configured():
        raise MailError("Email is not configured")
    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text)
    message.add_alternative(html, subtype="html")
    for filename, content, mime in attachments:
        maintype, _, subtype = mime.partition("/")
        message.add_attachment(content, maintype=maintype, subtype=subtype or "octet-stream", filename=filename)
    try:
        with connect() as server:
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(message)
    except (OSError, smtplib.SMTPException) as error:
        raise MailError(str(error)) from error


# Every email the portal sends: its name for admins and its subject line
EMAILS = {
    "invitation": {"label": "دعوة مستخدم جديد", "subject": "دعوة إلى {portal_name}"},
    "password_reset": {"label": "تعيين كلمة مرور جديدة", "subject": "تعيين كلمة مرور جديدة — {portal_name}"},
    "login_code": {"label": "رمز التحقق عند الدخول", "subject": "{code} رمز التحقق — {portal_name}"},
    "request_returned": {"label": "إعادة طلب للتعديل", "subject": "الطلب رقم {request_id} يحتاج تعديلًا — {portal_name}"},
    "request_approved": {"label": "اعتماد طلب", "subject": "تم اعتماد الطلب رقم {request_id} — {portal_name}"},
    "request_deleted": {"label": "حذف طلب", "subject": "حُذف الطلب رقم {request_id} — {portal_name}"},
    # To the client, not to a user: their invoice, how much is due and the link to see it
    "invoice_to_client": {"label": "إرسال الفاتورة للعميل", "subject": "الفاتورة #{invoice_no} من {company}"},
}

# How the company signs what goes to its clients
COMPANY = {
    "company": "FUTURE LIFE L.L.C O.P.C",
    "company_address": ["United Arab Emirates – Al Ain City – Downtown – Hessa Bint Mohammed Street",
                        "Opposite ADCB Bank and Al Ain Post Office", "ALAIN, Abu Dhabi 15975"],
    "company_phone": "+971557404950",
}


def compose(name: str, **values) -> tuple[str, str, str]:
    """The subject, plain-text body and HTML body of one email."""
    values = {**COMPANY, **values}
    subject = EMAILS[name]["subject"].format(portal_name=PORTAL_NAME, **values)
    return subject, *render(name, **values)


def send_login_code(to: str, full_name: str, code: str, minutes: int):
    """The 6-digit code for the second step of logging in."""
    send(to, *compose("login_code", full_name=full_name, code=code, minutes=minutes))


def send_password_link(to: str, full_name: str, username: str, link: str, hours: int, invited: bool):
    """The invitation for a new user, or the reset link for an existing one."""
    send(to, *compose("invitation" if invited else "password_reset", full_name=full_name, username=username,
                      email=to, link=link, hours=hours))


def compose_sample(name: str, to: str, full_name: str) -> tuple[str, str, str]:
    """An email filled with made-up values, for the admin's mail test page. Its link and code open nothing."""
    values = {
        "full_name": full_name, "username": "username", "email": to, "hours": settings.password_link_hours,
        "link": f"{settings.public_url.rstrip('/')}/set-password?token=sample", "code": "123456", "minutes": 10,
        "request_id": 1234, "form_label": "طلب بيع لعميل جديد", "customer_name": "عميل تجريبي", "reviewer": "مدير المبيعات",
        "reason": "رقم هاتف العميل ناقص، وصورة إثبات الدفع غير واضحة. صحّح البيانات وأعد الإرسال.",
        "invoice_no": "06538", "client_name": "عميل تجريبي", "due_date": "09/11/2026", "total": "1,250",
        "due": "1,200",
    }
    if name.startswith("request_"):
        values["link"] = f"{settings.public_url.rstrip('/')}/requests/{values['request_id']}"
    subject, text, html = compose(name, **values)
    return f"[تجربة] {subject}", text, html
