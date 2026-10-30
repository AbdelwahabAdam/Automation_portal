from ...modules.form_engine import FormSpec, register

from . import definition, hooks

register(FormSpec(
    key="quotation",                # stored on every request: never rename
    label="طلب عرض سعر",
    icon="file-text",
    description="تسجيل طلب عرض سعر",
    sections=definition.SECTIONS,
    # Approving it makes the offer itself in Daftra — an estimate, not an invoice — and the client
    # when the phone matches nobody. Nothing is paid and no work order is made.
    daftra_note="وتُنشأ في دفترة عرض السعر بالمنتجات المطلوبة، ويُنشأ العميل إن لم يكن مسجلًا. لا تُنشأ فاتورة ولا أمر شغل.",
    on_approve=hooks.on_approve,
))




