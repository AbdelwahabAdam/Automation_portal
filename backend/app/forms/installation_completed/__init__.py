from ...modules.form_engine import FormSpec, register

from . import definition

register(FormSpec(
    key="installation_completed",                # stored on every request: never rename
    label="تأكيد إتمام التركيب",
    icon="check-circle",
    description="تسجيل تأكيد الإتمام",
    sections=definition.SECTIONS,
    visible=False,          # no new requests; old ones still open and can be reviewed
))
