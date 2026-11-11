from ...modules.form_engine import FormAction, FormSpec, register

from . import definition, hooks

register(FormSpec(
    key="online_sale",             # stored on every request: never rename
    label="طلب بيع - دفع إلكتروني",
    icon="package",
    description="طلب بيع تُرسل فاتورته للعميل بالبريد ليدفعها، ثم يُنشأ أمر الشغل بعد الدفع",
    # Shown in the catalog, greyed out: staff can see it coming, and cannot start one yet
    ready=False,
    sections=definition.SECTIONS,
    daftra_note="ويُنشأ في دفترة العميل (إن كان جديدًا) والفاتورة، وتُرسل الفاتورة إلى بريد العميل، "
                "ويبقى الطلب «بانتظار الدفع» حتى يُنشأ أمر الشغل.",
    on_approve=hooks.on_approve,
    approved_status=hooks.AWAITING_PAYMENT,
    actions=(
        FormAction(
            key="create_work_order", label="إنشاء أمر الشغل", statuses=(hooks.AWAITING_PAYMENT,),
            run=hooks.create_work_order, fields=(definition.INSTALLATION_DAYS,), then_status="approved",
            confirm="تأكد أن العميل دفع الفاتورة. يُنشأ أمر الشغل في دفترة ويُغلق الطلب معتمدًا.",
        ),
        FormAction(
            key="resend_invoice_email", label="إعادة إرسال الفاتورة", statuses=(hooks.AWAITING_PAYMENT,),
            run=hooks.resend_invoice_email,
            confirm="تُرسل الفاتورة مرة أخرى إلى بريد العميل المكتوب في الطلب، بالمبلغ المستحق اليوم.",
        ),
    ),
))
