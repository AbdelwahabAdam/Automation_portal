"""What تقرير الزيارات اليومي asks: its sections, with one switch per field.

    HIDE  not asked      SHOW  asked, may be left empty      REQUIRED  must be filled
    REQUIRED_IF(when)    must be filled when `when` holds

A report, not a request about a client: it has no بيانات العميل, and its own بيانات التقرير.
"""

from ...modules.form_engine import REQUIRED, SHOW, f, files, money, shared, switched


def report_info(*, request_date, employee_name, visit_area):
    return switched(
        "بيانات التقرير",
        (request_date, f("request_date", "تاريخ التقرير", "date", default="today", not_future=True)),
        (employee_name, f("employee_name", "اسم الموظف", "auto_user")),
        (visit_area, f("visit_area", "المنطقة / خط السير")),
    )


def visits(*, visits_count, visits, new_leads, closed_sales, collected_amount, issues):
    return switched(
        "الزيارات",
        (visits_count, f("visits_count", "عدد الزيارات", "number", min=1, integer=True)),
        (visits, f("visits", "تفاصيل الزيارات: لكل زيارة سطر فيه العميل والمنطقة والغرض والنتيجة", "textarea",
                   max_length=6000)),
        (new_leads, f("new_leads", "عدد العملاء المهتمين الجدد", "number", min=0, integer=True)),
        (closed_sales, f("closed_sales", "عدد المبيعات المؤكدة", "number", min=0, integer=True)),
        (collected_amount, money("collected_amount", "إجمالي المبالغ المحصلة، إن وجدت")),
        (issues, f("issues", "مشاكل أو طلبات تحتاج متابعة", "textarea")),
    )


def attachments(*, visit_photos):
    return switched("المرفقات", (visit_photos, files("visit_photos", "صور من الزيارات، إن توفرت")))


SECTIONS = [
    report_info(request_date=REQUIRED, employee_name=SHOW, visit_area=SHOW),
    visits(visits_count=REQUIRED, visits=REQUIRED, new_leads=SHOW, closed_sales=SHOW, collected_amount=SHOW,
           issues=SHOW),
    attachments(visit_photos=SHOW),
    shared.notes(notes=SHOW),
]
