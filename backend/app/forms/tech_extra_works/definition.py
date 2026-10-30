"""The fields of اعمال اضافية (قسم الفنيات), as sections (form_engine has the building blocks)."""

from ...modules.form_engine import NOTES, PAID, amounts, client, f, money, payment, request_info, section

# This form offers these services and nothing else. They are named by their Daftra product id,
# which is the same on every copy of the portal — our own catalog ids are not.
# 194 «service» is «أخرى»: the work is described and priced on the line, and the invoice carries it
# as a service line, exactly as الكتابة المطلوبة does.
OTHER_WORK_DAFTRA_ID = 194
# What the form calls each of them, in the order it offers them. The names are the portal's own:
# the invoice carries the product's name as Daftra holds it (Water Connection Service and the rest),
# since that is what the accounts are kept in.
TECH_SERVICE_LABELS = {
    212: "تمديد المياة",                  # Water Connection Service — «Water extension»
    418: "تمديد الكهرباء",                # Electricity Connection Service — «Electricity extension»
    433: "اعمال باسكو",                   # interlocking paving Removel $ Breaking Service (code 2016)
    OTHER_WORK_DAFTRA_ID: "أخرى",         # the catalog's general «service», described on the line
}
TECH_SERVICE_DAFTRA_IDS = list(TECH_SERVICE_LABELS)

SECTIONS = [
    # The technical department does not always know which source the work came through
    request_info("تاريخ الطلب", invoiced=True, source_required=False),
    client(False),
    section(
        "تفاصيل الطلب",
        # Only the technical department's services, by their Daftra product id. «أخرى» is
        # described and priced on its own line, and can be added more than once.
        f("order_lines", "الأعمال المطلوبة", "order_lines", True, subtotal_field="total_amount",
          items="tech_services", item_ids=TECH_SERVICE_DAFTRA_IDS, item_labels=TECH_SERVICE_LABELS,
          line_fields=[
              f("work_description", "وصف العمل", "text", True, max_length=500,
                only_for=[OTHER_WORK_DAFTRA_ID]),
              money("work_price", "سعر الوحدة، شامل الضريبة (درهم)", True, positive=True,
                    only_for=[OTHER_WORK_DAFTRA_ID], line_price=True),
          ]),
        # Printed on the invoice as «الفني: …», which is how the technical department finds
        # its own work again in Daftra
        f("technician", "الفني (الموظف في دفترة)", "daftra_staff", True),
    ),
    amounts(total_label="قيمة الأعمال النهائية، شامل الضريبة", auto_total=True, invoiced=False,
            paid_label="المبلغ المدفوع فعليًا الآن", discounts=False),
    payment(when=PAID, invoiced=True),
    NOTES,
]
