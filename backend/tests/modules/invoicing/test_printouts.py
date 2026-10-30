"""The PDFs the portal draws itself (app.printouts)."""

from app import printouts

ROWS = [
    "نوع الجهاز: باقة برادة سقيا الخير - 2 صنبور - أبيض",
    "لون البرادة: أبيض — لون الغطاء: الابيض * خشابي مقاس طبيعي — لون القاعدة: أسود",
    "القطعة الأمامية: مائل — اتجاه الدبليو: عرضي — ظهر الكفر: بدون ظهر — تصميم جديد",
    "نوع الجهاز: باب خلفي جرار لبرادة مدمجة",
    "لون البرادة: أخرى",
    "العميل: عميل تجربة البوابة 2 — 0500000001",
    "العنوان: أبوظبي، منطقة أبوظبي، نورين، 700",
    "اللوكيشن: https://maps.app.goo.gl/JLjjF7ze4xYAbwcLA?g_st=ic",
    "الإحداثيات: 24.1787, 55.6045",
    "رقم الفاتورة: 06320",
    "المسؤول: alaa",
]
VALUES = {
    "inscription": "إنا أنزلناه في ليلة القدر", "plate_color": "اللون الابيض * خشابي مقاس طبيعي",
    "installation_accessories": "", "front_design": "مائل", "w_direction": "عرضي", "cover_back": "بدون ظهر",
    "design_version": "تصميم جديد", "cooler_color": "", "base_color": "لون القاعده ( الاسود)",
    "available_colors": "سقيا الخير - اللون الابيض * خشابي مقاس طبيعي / باب خلفي جرار لبرادة مدمجة – لون البرادة أخرى",
}


def work_order_html(**overrides) -> str:
    values = {
        "number": "00100102625", "title": "باقة برادة سقيا الخير - 2 صنبور - أبيض أبوظبي منطقة أبوظبي 4089",
        "start": "23/10/2026", "delivery": "07/11/2026", "rows": ROWS, "values": VALUES,
        "client_name": "عميل تجربة البوابة 2", "client_code": "004089", "phone": "0500000001",
        "address": "أبوظبي، منطقة أبوظبي، نورين، 700",
        "location_url": "https://maps.app.goo.gl/JLjjF7ze4xYAbwcLA?g_st=ic", "coordinates": "24.1787, 55.6045",
        "product_image": "", "invoice_no": "06320", "responsible": "alaa", "sales_person": "محمد",
        **overrides,
    }
    return printouts._env.get_template("work_order.html").render(**values)


def test_the_work_order_has_the_sections_daftra_prints():
    html = work_order_html()
    for heading in ("نموذج أمر تشغيل ومتابعة عقد", "بيانات العقد", "أمر الشغل ومتابعته", "بيانات العميل",
                    "بيانات الموظف المعين لأمر الشغل", "إعتماد ادخال البيانات", "إمضاء ادارة التصنيع"):
        assert heading in html, heading


def test_each_part_of_the_description_is_its_own_line():
    html = work_order_html()
    # One block per row, not one run of text
    for row in ROWS:
        assert f"<div>■ {row}</div>" in html, row


def test_the_work_order_comes_out_on_one_page():
    """Daftra's own form is one page, and a second page of signatures is no use on the floor."""
    from weasyprint import HTML
    document = HTML(string=work_order_html(), base_url=str(printouts.TEMPLATE_DIR)).render()
    assert len(document.pages) == 1
