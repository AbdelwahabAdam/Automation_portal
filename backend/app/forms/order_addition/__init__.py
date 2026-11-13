from ...modules.form_engine import FormSpec, register

from . import fields

register(FormSpec(
    key="order_addition",                # stored on every request: never rename
    label="طلب إضافة على طلب قائم",
    icon="plus",
    description="تسجيل إضافة مرتبطة بطلب",
    sections=fields.SECTIONS,
    visible=False,          # no new requests; old ones still open and can be reviewed
))
