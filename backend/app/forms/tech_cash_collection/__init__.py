from ...modules.form_engine import FormSpec, register

from . import fields

register(FormSpec(
    key="tech_cash_collection",                # stored on every request: never rename
    label="تسجيل تحصيل نقدي بواسطة الفني",
    icon="receipt",
    description="تسجيل التحصيل النقدي",
    sections=fields.SECTIONS,
    visible=False,          # no new requests; old ones still open and can be reviewed
))
