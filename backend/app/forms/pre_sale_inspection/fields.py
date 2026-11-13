"""What طلب معاينة قبل البيع asks: its sections, with one switch per field.

    HIDE  not asked      SHOW  asked, may be left empty      REQUIRED  must be filled
    REQUIRED_IF(when)    must be filled when `when` holds
"""

from ...modules.form_engine import HIDE, REQUIRED, SHOW, f, files, shared, switched


def order_details(*, site_type, product_name, inspection_purpose, preferred_date, preferred_time, site_contact):
    return switched(
        "تفاصيل الطلب",
        (site_type, f("site_type", "نوع الموقع", "select",
                      options=["منزل", "مسجد", "مدرسة", "مغسلة سيارات", "جمعية خيرية", "شركة", "أخرى"])),
        (product_name, f("product_name", "المنتج المبدئي المهتم به العميل، إن وجد", "product")),
        (inspection_purpose, f("inspection_purpose", "المطلوب من المعاينة", "textarea")),
        (preferred_date, f("preferred_date", "الموعد المفضل للمعاينة", "date")),
        (preferred_time, f("preferred_time", "الوقت المفضل", "select", options=["صباحًا", "ظهرًا", "مساءً"])),
        (site_contact, f("site_contact", "اسم ورقم الشخص المسؤول في الموقع، إن اختلف عن العميل")),
    )


def attachments(*, site_photos):
    return switched("المرفقات", (site_photos, files("site_photos", "صور الموقع، إن توفرت")))


SECTIONS = [
    shared.request_info(request_date=REQUIRED, employee_name=SHOW, order_source=HIDE, source=REQUIRED,
                        labels={"request_date": "تاريخ الطلب"}),
    shared.client(
        phone=REQUIRED, phone2=SHOW, client_code=SHOW, customer_name=REQUIRED, customer_type=SHOW, gender=SHOW,
        email=HIDE, labels={"customer_name": "اسم العميل / الجهة"},
    ),
    shared.address(
        category=REQUIRED, area=REQUIRED, emirate=REQUIRED, street=SHOW, house=SHOW, location_url=REQUIRED,
        coordinates=REQUIRED, title="عنوان المعاينة",
    ),
    order_details(site_type=REQUIRED, product_name=SHOW, inspection_purpose=REQUIRED, preferred_date=SHOW,
                  preferred_time=SHOW, site_contact=SHOW),
    attachments(site_photos=SHOW),
    shared.notes(notes=SHOW),
]
