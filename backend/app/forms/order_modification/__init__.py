from ...modules.form_engine import FormSpec, register

from . import definition

register(FormSpec(
    key="order_modification",                # stored on every request: never rename
    label="طلب تعديل على طلب قائم",
    icon="edit",
    description="تسجيل التعديل المطلوب",
    sections=definition.SECTIONS,
    visible=False,          # no new requests; old ones still open and can be reviewed
))
