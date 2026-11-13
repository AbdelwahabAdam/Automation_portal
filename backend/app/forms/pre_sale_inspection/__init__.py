from ...modules.form_engine import FormSpec, register

from . import fields

register(FormSpec(
    key="pre_sale_inspection",                # stored on every request: never rename
    label="طلب معاينة قبل البيع",
    icon="eye",
    description="تسجيل طلب معاينة",
    sections=fields.SECTIONS,
    visible=False,          # no new requests; old ones still open and can be reviewed
))
