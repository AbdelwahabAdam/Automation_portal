"""Building blocks a form's fields are written with: one field, and the few fields several forms
share as they are. The sections several forms share are in sections.py, one switch per field."""

from .inscriptions import OTHER_LABEL, inscription_choices
from .options import NO_INSCRIPTION, YES_NO


def f(name, label, type="text", required=False, **extra):
    return {"name": name, "label": label, "type": type, "required": required, **extra}


def money(name, label, required=False, **extra):
    # money=True: an amount in dirhams, which the form and the request's page print with its unit
    return f(name, label, "number", required, min=0, money=True, **extra)


# The line of a product sold without a fixed price (the catalog's «بدون سعر ثابت»), in a package or
# on its own: the salesperson types its price, and the text its invoice line carries, which starts
# as the product's own (default_from_product). Neither is asked of any other product.
OPEN_PRICE_FIELDS = [
    money("item_price", "سعر الوحدة، شامل الضريبة (درهم)", True, line_price=True, column=True, open_price_only=True),
    f("work_description", "نص البند في الفاتورة", "textarea", True, max_length=2000, open_price_only=True,
      default_from_product="description"),
]


def yes_no(name, label, required=True, **extra):
    return f(name, label, "select", required, options=YES_NO, **extra)


def files(name, label, required=False, **extra):
    return f(name, label, "files", required, **extra)


def original_refs():
    return [
        f("original_order", "رقم الطلب الأصلي، إن توفر"),
        f("original_invoice", "رقم الفاتورة الأصلية، إن توفر"),
        f("work_order", "رقم أمر الشغل، إن توفر"),
    ]


INSCRIPTION = [
    # Picked from the catalogue, whose codes the labels carry; what is saved and engraved is the
    # wording alone, so everything downstream (the invoice's service line, the work order) reads
    # it as it always did. «أخرى» is for anything the catalogue has not got, typed in by hand.
    # blank_value: left alone it saves as «لا يوجد», which is what the empty line of the list says,
    # so there is nothing to write and nothing to charge for.
    f("inscription", "الكتابة المطلوبة", "text", max_length=500, choices=inscription_choices(),
      other_label=OTHER_LABEL, blank_value=NO_INSCRIPTION[0]),
    f("inscription_place", "مكان الكتابة، إن وجدت"),
]
