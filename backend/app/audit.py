"""Writing audit log entries.

An entry is added to the same database session as the change it describes, so
the caller's commit saves both together and no change is saved without its entry.
"""

from fastapi import Depends
from fastapi import Request as HttpRequest
from sqlalchemy.orm import Session

from .database import get_db
from .forms import FORM_TYPES, form_fields
from .mail import EMAILS
from .models import AuditLog, Request, Role, User
from .pages import DEPARTMENT_LABELS, PAGES, department_of

ACTIONS = {
    "auth.login": "تسجيل دخول",
    "auth.login_failed": "محاولة دخول فاشلة",
    "auth.logout": "تسجيل خروج",
    "user.create": "إضافة مستخدم",
    "user.update": "تعديل مستخدم",
    "user.password_reset": "تغيير كلمة مرور مستخدم",
    "user.invite": "إرسال رابط كلمة المرور",
    "auth.password_reset_request": "طلب استعادة كلمة المرور",
    "auth.password_set": "تعيين كلمة المرور",
    "user.delete": "حذف مستخدم",
    "user.mfa_reset": "إيقاف التحقق بخطوتين لمستخدم",
    "auth.mfa_code_sent": "إرسال رمز التحقق بالبريد",
    "account.update": "تعديل الاسم من صفحة حسابي",
    "account.password_change": "تغيير كلمة المرور من صفحة حسابي",
    "account.mfa_enabled": "تفعيل التحقق بخطوتين",
    "account.mfa_disabled": "إيقاف التحقق بخطوتين",
    "role.create": "إضافة دور",
    "role.update": "تعديل دور",
    "role.delete": "حذف دور",
    "request.create": "إنشاء طلب",
    "request.update": "تعديل مسودة طلب",
    "request.submit": "إرسال طلب",
    "request.delete": "حذف مسودة طلب",
    "request.approve": "اعتماد طلب",
    "request.daftra_failed": "تعذر إنشاء الفاتورة في دفترة",
    "request.return": "إعادة طلب للتعديل",
    "attachment.upload": "رفع مرفق",
    "attachment.download": "فتح مرفق",
    "attachment.delete": "حذف مرفق",
    "audit.export": "تصدير سجل النشاط",
    "mail.test": "إرسال بريد تجريبي",
    "product.create": "إضافة منتج",
    "product.update": "تعديل منتج",
    "product.delete": "حذف منتج",
    "package.create": "إضافة باقة",
    "package.update": "تعديل باقة",
    "package.delete": "حذف باقة",
}

ENTITY_TYPES = {"user": "مستخدم", "role": "دور", "request": "طلب", "attachment": "مرفق", "product": "منتج",
                "package": "باقة"}

# Labels for the keys that appear in the before/after values of an entry
FIELD_LABELS = {
    **{spec["name"]: spec["label"] for form_type in FORM_TYPES for spec in form_fields(form_type)},
    "username": "اسم المستخدم",
    "email": "البريد الإلكتروني",
    "email_sent": "تم إرسال البريد",
    "template": "الرسالة",
    "name_ar": "الاسم بالعربية",
    "description": "الوصف",
    "unit_price": "سعر الوحدة",
    "price_includes_tax": "السعر شامل الضريبة",
    "tax_rate": "نسبة الضريبة",
    "code": "الكود",
    "color": "اللون",
    "total": "الإجمالي",
    "items": "المنتجات",
    "full_name": "الاسم",
    "is_admin": "مدير النظام",
    "is_active": "الحساب مفعّل",
    "roles": "الأدوار",
    "manages": "يدير الأقسام",
    "reason": "السبب",
    "name": "الاسم",
    "pages": "الصفحات",
    "form_type": "نوع النموذج",
    "status": "الحالة",
    "field": "حقل المرفق",
    "filename": "اسم الملف",
    "size": "الحجم (بايت)",
    "rows": "عدد السجلات",
    "order_source_name": "مصدر الطلب في دفترة",
    "category_name": "التصنيف",
    "invoice_name": "الفاتورة",
    "treasury_name": "الخزينة في دفترة",
    "daftra_invoice_no": "رقم الفاتورة في دفترة",
    "daftra_receipt_no": "رقم سند القبض في دفترة",
    "daftra_work_order_no": "رقم أمر الشغل في دفترة",
    "invoice_pdf_saved": "تم حفظ PDF الفاتورة",
    "receipt_pdf_saved": "تم حفظ PDF سند القبض",
    "work_order_pdf_saved": "تم حفظ PDF أمر الشغل",
    "work_order_fields_saved": "تم ملء حقول أمر الشغل في دفترة",
    "error": "الخطأ",
    "daftra_staff_id": "رقم الموظف في دفترة",
}

# Readable names for stored values such as page keys and form types
VALUE_LABELS = {
    **{key: definition["label"] for key, definition in FORM_TYPES.items()},
    **{
        page["key"]: DEPARTMENT_LABELS[department_of(page["key"])] + " / " + page["label"]
        for page in PAGES
    },
    **DEPARTMENT_LABELS,
    **{key: email["label"] for key, email in EMAILS.items()},
    "draft": "مسودة",
    "submitted": "قيد المراجعة",
    "returned": "تحتاج تعديل",
    "approved": "معتمد",
}


def changes(before: dict, after: dict) -> tuple[dict, dict]:
    """Keeps only the keys whose value differs between the two."""
    changed = [key for key in before.keys() | after.keys() if before.get(key) != after.get(key)]
    return {k: before[k] for k in changed if k in before}, {k: after[k] for k in changed if k in after}


def user_snapshot(user: User) -> dict:
    return {
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "is_admin": user.is_admin,
        "is_active": user.is_active,
        "roles": sorted(role.name for role in user.roles),
        "manages": sorted(user.manages),
        "daftra_staff_id": user.daftra_staff_id,
    }


def role_snapshot(role: Role) -> dict:
    return {"name": role.name, "pages": sorted(role.pages)}


def request_label(request: Request) -> str:
    customer = request.data.get("customer_name")
    return f"طلب {request.id} — {customer}" if customer else f"طلب {request.id}"


class Audit:
    """Request-scoped writer: knows the caller's address and shares the endpoint's session."""

    def __init__(self, http_request: HttpRequest, db: Session = Depends(get_db)):
        self.db = db
        self.ip = http_request.client.host if http_request.client else ""
        self.user_agent = (http_request.headers.get("user-agent") or "")[:300]

    def log(self, actor: User | None, action: str, entity_type: str = "", entity_id: int | None = None,
            entity_label: str = "", before: dict | None = None, after: dict | None = None,
            username: str = ""):
        self.db.add(AuditLog(
            user_id=actor.id if actor else None,
            username=(actor.username if actor else username)[:50],
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_label=entity_label[:160],
            before=before or None,
            after=after or None,
            ip=self.ip,
            user_agent=self.user_agent,
        ))
