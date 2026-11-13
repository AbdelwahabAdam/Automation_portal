from ...modules.form_engine import FormSpec, register

from . import fields, output

register(FormSpec(
    key="new_sale",                # stored on every request: never rename
    label="طلب بيع لعميل جديد",
    icon="package",
    description="تسجيل طلب بيع جديد",
    sections=fields.SECTIONS,
    daftra_note="ويُنشأ في دفترة العميل (إن كان جديدًا) والفاتورة وسند القبض بالمبلغ المدفوع، وأمر الشغل إن طُلب.",
    on_approve=output.on_approve,
))
