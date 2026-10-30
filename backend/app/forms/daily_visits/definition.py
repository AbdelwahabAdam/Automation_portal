"""The fields of تقرير الزيارات اليومي, as sections (form_engine has the building blocks)."""

from ...modules.form_engine import NOTES, attachments, f, files, money, section

SECTIONS = [
    section(
        "بيانات التقرير",
        f("request_date", "تاريخ التقرير", "date", True, default="today", not_future=True),
        f("employee_name", "اسم الموظف", "auto_user"),
        f("visit_area", "المنطقة / خط السير"),
    ),
    section(
        "الزيارات",
        f("visits_count", "عدد الزيارات", "number", True, min=1, integer=True),
        f("visits", "تفاصيل الزيارات: لكل زيارة سطر فيه العميل والمنطقة والغرض والنتيجة", "textarea", True, max_length=6000),
        f("new_leads", "عدد العملاء المهتمين الجدد", "number", min=0, integer=True),
        f("closed_sales", "عدد المبيعات المؤكدة", "number", min=0, integer=True),
        money("collected_amount", "إجمالي المبالغ المحصلة، إن وجدت"),
        f("issues", "مشاكل أو طلبات تحتاج متابعة", "textarea"),
    ),
    attachments(files("visit_photos", "صور من الزيارات، إن توفرت")),
    NOTES,
]
