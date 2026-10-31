"""How an activity-log entry reads: the label for every action, record type, field and value.

A module that has labels of its own adds them with `add_value_labels`, rather than this file
reaching into every module to ask — which would make audit and those modules import each other.
Old entries keep their old keys, so a label is never removed, only added to.
"""

from functools import cache

from ...core import permissions
from ..form_engine import all_forms

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
    "client.address.add": "إضافة عنوان لعميل",
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
    "daftra.sync": "مزامنة مع دفترة",
    "order_source.create": "إضافة مصدر طلب في دفترة",
    "order_source.update": "تفعيل أو إيقاف مصدر طلب في دفترة",
    "product.daftra_sync": "تحديث منتج من دفترة",
}

ENTITY_TYPES = {"user": "مستخدم", "role": "دور", "request": "طلب", "attachment": "مرفق", "product": "منتج",
                "package": "باقة", "client": "عميل", "order_source": "مصدر طلب"}

# Labels for the keys that appear in the before/after values of an entry.
# A function, not a table: the forms register themselves as they are imported, so reading them
# while this module is still being imported would see none of them.
_OWN_FIELD_LABELS = {
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
    "kinds": "ما تمت مزامنته",
    "active": "مفعّل",
    "pages": "الصفحات",
    "permissions": "الصلاحيات",
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
    "payment_proof_sent": "تم إرفاق إثبات الدفع بالفاتورة في دفترة",
    "work_order_pdf_saved": "تم حفظ PDF أمر الشغل",
    "work_order_fields_saved": "تم ملء حقول أمر الشغل في دفترة",
    "work_order_sales_assigned": "تم تعيين موظف المبيعات على أمر الشغل في دفترة",
    "error": "الخطأ",
    "is_default": "العنوان الأساسي",
    "daftra_staff_id": "رقم الموظف في دفترة",
}

# Readable names for stored values such as page keys and form types. The emails' own names are
# added by notifications (add_value_labels), so audit does not import it.
# What a page key meant before access became per form. Old entries still carry these, so the
# labels stay: an entry from before the change must still read (final_plan.md §6).
LEGACY_PAGE_LABELS = {
    "sales": "المبيعات", "data_entry": "إدخال البيانات", "accounting": "الحسابات",
    "operations": "أوامر الشغل والتركيبات", "admin": "الإدارة",
    "sales.new_request": "المبيعات / النماذج",
    "sales.my_requests": "المبيعات / طلباتي",
    "sales.review": "المبيعات / المراجعة",
    "data_entry.home": "إدخال البيانات / إدخال البيانات",
    "accounting.home": "الحسابات / الحسابات",
    "operations.home": "أوامر الشغل والتركيبات / أوامر الشغل والتركيبات",
    "admin.users": "الإدارة / المستخدمون",
    "admin.permissions": "الإدارة / الأدوار والصلاحيات",
    "admin.audit": "الإدارة / سجل النشاط",
    "admin.catalog": "الإدارة / المنتجات والباقات",
    "admin.daftra_sync": "الإدارة / المزامنة مع دفترة",
    "admin.order_sources": "الإدارة / مصادر الطلب",
    "admin.mail": "الإدارة / اختبار البريد",
}

_OWN_VALUE_LABELS = {
    **LEGACY_PAGE_LABELS,
    "draft": "مسودة",
    "submitted": "قيد المراجعة",
    "returned": "تحتاج تعديل",
    "approved": "معتمد",
}

# What other modules add about themselves (e.g. notifications' email names)
_added_value_labels: dict[str, str] = {}


def add_value_labels(labels: dict[str, str]):
    """A module says how its own stored values read. Called as that module is imported."""
    _added_value_labels.update(labels)
    value_labels.cache_clear()


@cache
def field_labels() -> dict:
    """Every field of every form, plus the keys that are not a form's."""
    from_forms = {spec["name"]: spec["label"] for form in all_forms() for spec in form.fields()}
    return {**from_forms, **_OWN_FIELD_LABELS}


@cache
def value_labels() -> dict:
    """Every stored value that has a name: the forms, today's permissions, the old page keys, and
    whatever other modules added about themselves."""
    from_permissions = {p.key: p.label for p in permissions.all_permissions()}
    return {**{form.key: form.label for form in all_forms()}, **from_permissions,
            **_OWN_VALUE_LABELS, **_added_value_labels}
