from ...modules.form_engine import FormSpec, register

from . import definition

register(FormSpec(
    key="quote_to_invoice",                # stored on every request: never rename
    label="طلب تحويل عرض سعر إلى فاتورة",
    icon="copy",
    description="تحويل عرض سعر معتمد إلى فاتورة",
    sections=definition.SECTIONS,
    visible=False,          # no new requests; old ones still open and can be reviewed
))
