from ...modules.form_engine import FormSpec, register

from . import fields

register(FormSpec(
    key="data_entry_error",                # stored on every request: never rename
    label="تبليغ خطأ إدخال بيانات",
    icon="alert-triangle",
    description="مطلوب تصحيح",
    sections=fields.SECTIONS,
    visible=False,          # no new requests; old ones still open and can be reviewed
))
