from ...modules.form_engine import FormSpec, register

from . import definition

register(FormSpec(
    key="contract_service_done",                # stored on every request: never rename
    label="تأكيد إنجاز خدمة مشمولة بالعقد",
    icon="shield",
    description="تسجيل إنجاز الخدمة",
    sections=definition.SECTIONS,
    visible=False,          # no new requests; old ones still open and can be reviewed
))
