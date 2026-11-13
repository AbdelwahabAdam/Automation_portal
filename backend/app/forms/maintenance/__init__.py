from ...modules.form_engine import FormSpec, register

from . import fields, output

register(FormSpec(
    key="maintenance",                # stored on every request: never rename
    label="طلب صيانة وتبديل",
    icon="tool",
    description="صيانة وتبديل فلاتر",
    sections=fields.SECTIONS,
    daftra_note="ويُنشأ في دفترة العميل (إن كان جديدًا) وفاتورة البنود المختارة، وسند القبض إن وُجدت دفعة.",
    on_approve=output.on_approve,
))
