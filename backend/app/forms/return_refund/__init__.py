from ...modules.form_engine import FormSpec, register

from . import definition

register(FormSpec(
    key="return_refund",                # stored on every request: never rename
    label="طلب مرتجع ورد مبلغ",
    icon="history",
    description="تسجيل المرتجع ورد المبلغ",
    sections=definition.SECTIONS,
    visible=False,          # no new requests; old ones still open and can be reviewed
))
