from ...modules.form_engine import FormSpec, register

from . import definition

register(FormSpec(
    key="tech_cash_collection",                # stored on every request: never rename
    label="تسجيل تحصيل نقدي بواسطة الفني",
    icon="receipt",
    description="تسجيل التحصيل النقدي",
    sections=definition.SECTIONS,
    visible=False,          # no new requests; old ones still open and can be reviewed
))
