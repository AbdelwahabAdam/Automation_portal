from ...modules.form_engine import FormSpec, register

from . import definition

register(FormSpec(
    key="daily_visits",                # stored on every request: never rename
    label="تقرير الزيارات اليومي",
    icon="map-pin",
    description="تسجيل تقرير الزيارات",
    sections=definition.SECTIONS,
    visible=False,          # no new requests; old ones still open and can be reviewed
))
