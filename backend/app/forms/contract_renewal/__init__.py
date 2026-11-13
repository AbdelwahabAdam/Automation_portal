from ...modules.form_engine import FormSpec, register

from . import fields, output

register(FormSpec(
    key="contract_renewal",                # stored on every request: never rename
    label="طلب تجديد عقد الصيانة السنوي",
    icon="calendar",
    description="تجديد عقد الصيانة",
    sections=fields.SECTIONS,
    daftra_note="ويُحدَّث تصنيف العميل في دفترة، وتُنشأ فاتورة التجديد وسند القبض بالمبلغ المدفوع.",
    on_approve=output.on_approve,
))
