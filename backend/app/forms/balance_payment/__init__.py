from ...modules.form_engine import FormSpec, register

from . import definition, hooks

register(FormSpec(
    key="balance_payment",                # stored on every request: never rename
    label="طلب تسديد مبلغ متبقي",
    icon="send",
    description="سداد المبلغ المتبقي على طلب",
    sections=definition.SECTIONS,
    daftra_note="ويُنشأ في دفترة سند قبض بالمبلغ المدفوع على الفاتورة المختارة.",
    validate=hooks.validate,
    on_approve=hooks.on_approve,
))
