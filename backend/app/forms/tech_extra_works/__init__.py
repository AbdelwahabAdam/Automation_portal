from ...modules.form_engine import FormSpec, register

from . import definition, hooks

register(FormSpec(
    key="tech_extra_works",                # stored on every request: never rename
    label="اعمال اضافية (قسم الفنيات)",
    # The form had neither when it was written; picked here, where a form says how it looks
    icon="settings",
    description="تسجيل أعمال إضافية للفنيات",
    sections=definition.SECTIONS,
    # Approving it invoices the extra works to a client Daftra already has, and makes the receipt
    # for whatever was paid now. No address is asked for, so no client can be created here.
    daftra_note="وتُنشأ في دفترة فاتورة الأعمال المختارة، وسند القبض إن وُجدت دفعة. العميل يجب أن يكون مسجلًا في دفترة.",
    on_approve=hooks.on_approve,
))
