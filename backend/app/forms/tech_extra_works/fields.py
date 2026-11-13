"""What اعمال اضافية (قسم الفنيات) asks: its sections, with one switch per field.

    HIDE  not asked      SHOW  asked, may be left empty      REQUIRED  must be filled
    REQUIRED_IF(when)    must be filled when `when` holds
"""

from ...modules.form_engine import (CASH_PAYMENT, HIDE, PAID, REQUIRED, REQUIRED_IF, SHOW, f, money, shared,
                                    switched, switched_fields)

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
# What each costs on this form, whatever the catalog says: the catalog's price is what they cost
# sold alone on the other forms, and a package has its own (150). «أخرى» is priced on its line.
TECH_SERVICE_PRICES = {212: 6, 418: 7, 433: 10}


# ---------- this form's own sections ----------

def order_details(*, order_lines, work_description, work_price, technician):
    """تفاصيل الطلب: only the technical department's services, by their Daftra product id. «أخرى»
    is described and priced on its own line (work_description, work_price), and can be added
    more than once."""
    return switched(
        "تفاصيل الطلب",
        (order_lines, f("order_lines", "الأعمال المطلوبة", "order_lines", subtotal_field="total_amount",
                        items="tech_services", item_ids=TECH_SERVICE_DAFTRA_IDS, item_labels=TECH_SERVICE_LABELS,
                        fixed_prices=TECH_SERVICE_PRICES, line_fields=switched_fields(
                            (work_description, f("work_description", "وصف العمل", "text", max_length=500,
                                                 only_for=[OTHER_WORK_DAFTRA_ID])),
                            (work_price, money("work_price", "سعر الوحدة، شامل الضريبة (درهم)", positive=True,
                                               only_for=[OTHER_WORK_DAFTRA_ID], line_price=True)),
                        ))),
        # Printed on the invoice as «الفني: …», which is how the technical department finds its own
        # work again in Daftra
        (technician, f("technician", "الفني (الموظف في دفترة)", "daftra_staff")),
    )


# ---------- the form ----------

SECTIONS = [
    shared.request_info(
        request_date=REQUIRED,
        employee_name=SHOW,
        order_source=SHOW,                   # the department does not always know the source
        source=HIDE,
        labels={"request_date": "تاريخ الطلب"},
    ),
    shared.client(
        phone=REQUIRED,
        phone2=SHOW,
        client_code=SHOW,
        customer_name=REQUIRED,
        customer_type=SHOW,
        gender=SHOW,
        email=HIDE,                          # no client is made here
    ),
    order_details(
        order_lines=REQUIRED,
        work_description=REQUIRED,
        work_price=REQUIRED,
        technician=REQUIRED,
    ),
    shared.amounts(
        subtotal_amount=HIDE,
        total_amount=SHOW,                   # the works' own total: no discount here
        discount_label=HIDE,
        discount_amount=HIDE,
        discount_approved_by=HIDE,
        paid_amount=REQUIRED,
        remaining_amount=SHOW,
        remaining_due_date=SHOW,
        labels={"total_amount": "قيمة الأعمال النهائية، شامل الضريبة",
                "paid_amount": "المبلغ المدفوع فعليًا الآن"},
    ),
    shared.payment(
        payment_method=REQUIRED_IF(PAID),
        treasury=REQUIRED_IF(PAID),
        payment_date=REQUIRED_IF(PAID),
        payment_reference=REQUIRED_IF(PAID),
        collector_name=REQUIRED_IF(CASH_PAYMENT),
    ),
    shared.notes(notes=SHOW),
]
