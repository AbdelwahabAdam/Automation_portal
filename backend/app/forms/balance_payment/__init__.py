from ...modules.form_engine import FormSpec, register

from . import fields, output

register(FormSpec(
    key="balance_payment",                # stored on every request: never rename
    label="طلب تسديد مبلغ متبقي",
    icon="send",
    description="سداد المبلغ المتبقي على طلب",
    sections=fields.SECTIONS,
    daftra_note="ويُنشأ في دفترة سند قبض بالمبلغ المدفوع على الفاتورة المختارة.",
    validate=fields.validate,
    on_approve=output.on_approve,
))
