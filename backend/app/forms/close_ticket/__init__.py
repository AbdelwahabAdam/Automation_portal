from ...modules.form_engine import FormSpec, register

from . import fields

register(FormSpec(
    key="close_ticket",                # stored on every request: never rename
    label="إغلاق بلاغ صيانة وأعطال",
    icon="x-circle",
    description="تسجيل إغلاق البلاغ",
    sections=fields.SECTIONS,
    visible=False,          # no new requests; old ones still open and can be reviewed
))
