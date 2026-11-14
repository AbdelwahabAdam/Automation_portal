"""The PDFs the portal draws itself (app.printouts)."""

from app.modules.invoicing import printouts

# الوصف is what is built; the client, the address and the rest have sections of their own
ROWS = [
    "نوع الجهاز: باقة برادة سقيا الخير - 2 صنبور - أبيض",
    "لون البرادة: أبيض — لون الغطاء: الابيض * خشابي مقاس طبيعي — لون القاعدة: أسود",
    "القطعة الأمامية: مائل — اتجاه الدبليو: عرضي — ظهر الكفر: بدون ظهر — تصميم جديد",
    "نوع الجهاز: باب خلفي جرار لبرادة مدمجة",
    "لون البرادة: أخرى",
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
        "days": "20", "device": "باقة برادة سقيا الخير - 2 صنبور - أبيض",
        **overrides,
    }
    return printouts._env.get_template("work_order.html").render(**values)


def test_the_work_order_has_the_seven_sections_daftra_prints():
    """Its own form, section for section, so the two can be read side by side."""
    html = work_order_html()
    for heading in ("نموذج أمر تشغيل ومتابعة عقد", "بيانات العقد", "بيانات العميل", "مواصفات الجهاز",
                    "ملحقات التركيب", "أمر الشغل ومتابعته", "الموظفون المعيّنون لأمر الشغل",
                    "التوقيعات والاعتمادات"):
        assert heading in html, heading
    # The four it is signed off by, in Daftra's own order
    for column in ("اعتماد إدخال البيانات", "إدارة المخزن", "إدارة التصنيع", "إدارة الفنيات"):
        assert column in html, column


def test_the_location_is_a_link_and_not_an_address_to_read_out():
    html = work_order_html()
    assert '<a href="https://maps.app.goo.gl/JLjjF7ze4xYAbwcLA?g_st=ic">فتح الموقع على الخريطة</a>' in html
    # Nothing to link to: the row is left for the floor to fill in
    assert "فتح الموقع على الخريطة" not in work_order_html(location_url="")


def test_the_contract_block_carries_the_numbers_and_the_days():
    html = work_order_html()
    for value in ("00100102625", "06320", "23/10/2026", "07/11/2026", "20 يومًا"):
        assert value in html, value


def test_the_client_and_the_staff_have_sections_of_their_own():
    """They used to be lines of الوصف; the form Daftra prints gives each its own row."""
    html = work_order_html()
    for value in ("عميل تجربة البوابة 2", "004089", "0500000001", "أبوظبي، منطقة أبوظبي، نورين، 700",
                  "محمد", "alaa"):
        assert value in html, value


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


def test_the_extensions_line_is_printed_when_there_are_any():
    """Daftra's own form leaves «التمديدات» blank for the floor; we print it when the request has it."""
    assert "التمديدات" in work_order_html()
    filled = work_order_html(values={**VALUES, "extensions": "تمديد الكهرباء، اعمال الحفر"})
    assert "تمديد الكهرباء، اعمال الحفر" in filled
