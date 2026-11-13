"""What تأكيد إنجاز خدمة مشمولة بالعقد asks: its sections, with one switch per field.

    HIDE  not asked      SHOW  asked, may be left empty      REQUIRED  must be filled
    REQUIRED_IF(when)    must be filled when `when` holds
"""

from ...modules.form_engine import HIDE, REQUIRED, SHOW, f, files, shared, switched


def service_details(*, contract_number, visit_number, services_done, service_date, technician_name, parts,
                    cooler_notes, next_visit_date):
    return switched(
        "تفاصيل الخدمة",
        (contract_number, f("contract_number", "رقم العقد / الفاتورة")),
        (visit_number, f("visit_number", "رقم الزيارة في العقد", "select",
                         options=["الزيارة الأولى", "الزيارة الثانية", "الزيارة الثالثة", "الزيارة الرابعة",
                                  "زيارة إضافية"])),
        (services_done, f("services_done", "الخدمات المنفذة", "multiselect",
                          options=["تبديل فلاتر", "صيانة البرادة", "تنظيف", "فحص"])),
        (service_date, f("service_date", "تاريخ التنفيذ", "date", not_future=True)),
        (technician_name, f("technician_name", "اسم الفني", "staff")),
        (parts, f("parts", "القطع والفلاتر المستبدلة وكمياتها", "textarea")),
        (cooler_notes, f("cooler_notes", "ملاحظات على حالة البرادة، إن وجدت", "textarea")),
        (next_visit_date, f("next_visit_date", "موعد الزيارة القادمة، إن تحدد", "date")),
    )


def attachments(*, service_photos, signed_report):
    return switched(
        "المرفقات",
        (service_photos, files("service_photos", "صور قبل وبعد الخدمة، إن توفرت")),
        (signed_report, files("signed_report", "تقرير الزيارة الموقّع، إن توفر")),
    )


SECTIONS = [
    shared.request_info(request_date=REQUIRED, employee_name=SHOW, order_source=HIDE, source=REQUIRED,
                        labels={"request_date": "تاريخ الطلب"}),
    shared.client(
        phone=REQUIRED, phone2=SHOW, client_code=REQUIRED, customer_name=REQUIRED, customer_type=SHOW, gender=SHOW,
        email=HIDE, labels={"customer_name": "اسم العميل"},
    ),
    service_details(
        contract_number=REQUIRED,
        visit_number=REQUIRED,
        services_done=REQUIRED,
        service_date=REQUIRED,
        technician_name=REQUIRED,
        parts=SHOW,
        cooler_notes=SHOW,
        next_visit_date=SHOW,
    ),
    attachments(service_photos=SHOW, signed_report=SHOW),
    shared.notes(notes=SHOW),
]
