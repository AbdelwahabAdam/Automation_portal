from ...modules.form_engine import FormSpec, register

from . import fields

register(FormSpec(
    key="installation_completed",                # stored on every request: never rename
    label="تأكيد إتمام التركيب",
    icon="check-circle",
    description="تسجيل تأكيد الإتمام",
    sections=fields.SECTIONS,
    visible=False,          # no new requests; old ones still open and can be reviewed
))
