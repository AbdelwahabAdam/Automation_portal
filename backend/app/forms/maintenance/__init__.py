from ...modules.form_engine import FormSpec, register

from . import definition, hooks

register(FormSpec(
    key="maintenance",                # stored on every request: never rename
    label="طلب صيانة وتبديل",
    icon="tool",
    description="صيانة وتبديل فلاتر",
    sections=definition.SECTIONS,
    daftra_note="ويُنشأ في دفترة العميل (إن كان جديدًا) وفاتورة البنود المختارة، وسند القبض إن وُجدت دفعة.",
    on_approve=hooks.on_approve,
))
