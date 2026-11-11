"""The fields of طلب بيع - دفع إلكتروني: طلب بيع لعميل جديد's own, with these differences.

- بيانات العميل asks every client for an email (not only a new one): the invoice is emailed to it,
  and it is put on the client in Daftra.
- قيمة الطلب starts المبلغ المدفوع فعليًا الآن at 0, and takes 0: the client pays the invoice later.
- المرفقات asks for nothing.
- التركيب وأمر الشغل is gone: the work order is made from the request once it is paid
  («إنشاء أمر الشغل», which asks for مدة التركيب then).

Everything else is طلب بيع's own sections, so a change there is a change here.
"""

from ...modules.form_engine import amounts, f
from ..new_sale import definition as sale

EMAIL = f("email", "البريد الإلكتروني للعميل", "email", True,
          placeholder="تُرسل إليه الفاتورة ورابط مشاهدتها")
# The section that is طلب بيع's work order, left out here
WORK_ORDER_SECTION = "التركيب وأمر الشغل"


def _client(spec: dict) -> dict:
    """بيانات العميل with an email every client is asked for, in place of the new client's own."""
    fields = [field for field in spec["fields"] if field["name"] != "email"]
    return {**spec, "fields": [*fields, EMAIL]}


def _amounts() -> dict:
    """قيمة الطلب as طلب بيع's, but nothing has to be paid now, and المبلغ المدفوع starts at 0."""
    built = amounts(must_pay=False, auto_total=True, invoiced=True)
    fields = [{**field, "default": "0"} if field["name"] == "paid_amount" else field for field in built["fields"]]
    return {**built, "fields": fields}


def _optional(spec: dict) -> dict:
    """المرفقات with nothing required."""
    return {**spec, "fields": [{**field, "required": False} for field in spec["fields"]]}


def _section(spec: dict) -> dict:
    return {"بيانات العميل": _client, "قيمة الطلب": lambda _: _amounts(), "المرفقات": _optional}.get(
        spec["title"], lambda same: same)(spec)


SECTIONS = [_section(spec) for spec in sale.SECTIONS if spec["title"] != WORK_ORDER_SECTION]

# What the request asks for when its work order is made, after it is paid
INSTALLATION_DAYS = f("installation_days", "مدة التركيب (بالأيام)", "number", True, integer=True, min=1,
                      max=sale.MAX_INSTALLATION_DAYS, placeholder="مثال: 15 أو 20", unit="يومًا")

