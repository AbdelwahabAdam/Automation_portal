from ...modules.form_engine import FormSpec, register

from . import definition

register(FormSpec(
    key="open_ticket",                # stored on every request: never rename
    label="فتح بلاغ صيانة وأعطال",
    icon="alert-circle",
    description="تسجيل بلاغ جديد",
    sections=definition.SECTIONS,
    visible=False,          # no new requests; old ones still open and can be reviewed
))
