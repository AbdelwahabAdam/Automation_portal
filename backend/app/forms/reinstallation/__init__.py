from ...modules.form_engine import FormSpec, register

from . import fields

register(FormSpec(
    key="reinstallation",                # stored on every request: never rename
    label="طلب إعادة تركيب",
    icon="refresh",
    description="تسجيل طلب إعادة تركيب",
    sections=fields.SECTIONS,
    visible=False,          # no new requests; old ones still open and can be reviewed
))
