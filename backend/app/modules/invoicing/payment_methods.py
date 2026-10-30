"""Our payment methods as Daftra's payment method keys.

Found on the account's existing payments: Tabby payments are recorded there as "visa" into the
«مدفوعات تابي» treasury. Written out in full rather than zipped against the forms' list, so
reordering the choices a form offers cannot quietly send payments to the wrong Daftra key —
`test_payment_methods_cover_every_choice` checks the two still match.
"""

PAYMENT_METHOD_KEYS = {
    "تحويل بنكي": "bank",
    "نقدًا": "cash",
    "ماكينة POS": "GEIDEA",
    "تابي": "visa",
    "تمارا": "_tamara",
    "طلب من الموقع": "Apple_pay",
}
