"""What فتح بلاغ صيانة وأعطال asks: its sections, with one switch per field.

    HIDE  not asked      SHOW  asked, may be left empty      REQUIRED  must be filled
    REQUIRED_IF(when)    must be filled when `when` holds
"""

from ...modules.form_engine import HIDE, REQUIRED, SHOW, f, files, shared, switched


def ticket_details(*, device_type, related_number, problem, coverage, urgency, preferred_date):
    return switched(
        "تفاصيل البلاغ",
        (device_type, f("device_type", "الجهاز / البرادة")),
        (related_number, f("related_number", "رقم العقد أو الفاتورة المرتبطة، إن توفر")),
        (problem, f("problem", "وصف العطل كما ذكره العميل", "textarea")),
        (coverage, f("coverage", "تغطية الإصلاح", "select", options=["ضمان", "عقد صيانة", "مدفوع", "غير معروف"])),
        (urgency, f("urgency", "الأولوية", "select", options=["عادي", "عاجل", "طارئ"])),
        (preferred_date, f("preferred_date", "الموعد المفضل للزيارة، إن وجد", "date")),
    )


def attachments(*, fault_media):
    return switched("المرفقات", (fault_media, files("fault_media", "صور / فيديو العطل، إن توفرت")))


SECTIONS = [
    shared.request_info(request_date=REQUIRED, employee_name=SHOW, order_source=HIDE, source=REQUIRED,
                        labels={"request_date": "تاريخ البلاغ"}),
    shared.client(
        phone=REQUIRED, phone2=SHOW, client_code=SHOW, customer_name=REQUIRED, customer_type=SHOW, gender=SHOW,
        email=HIDE, labels={"customer_name": "اسم العميل"},
    ),
    shared.address(
        category=REQUIRED, area=REQUIRED, emirate=REQUIRED, street=SHOW, house=SHOW, location_url=REQUIRED,
        coordinates=REQUIRED,
    ),
    ticket_details(device_type=REQUIRED, related_number=SHOW, problem=REQUIRED, coverage=REQUIRED, urgency=REQUIRED,
                   preferred_date=SHOW),
    attachments(fault_media=SHOW),
    shared.notes(notes=SHOW),
]
