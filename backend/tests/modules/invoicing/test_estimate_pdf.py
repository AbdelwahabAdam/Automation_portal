"""The عرض سعر PDF the portal draws: Daftra's link for an estimate's PDF does not open, and its API
cannot download one (checked on the live account, estimate 00347, 2026-11-14)."""

from types import SimpleNamespace

from app.modules.invoicing import printouts
from app.modules.invoicing.estimate import draw_estimate, html_lines

# Estimate 00347 as the live account returned it, cut to what the PDF reads
ESTIMATE = {
    "no": "00347", "date": "12/11/2026", "original_date": "2026-11-12", "summary_total": 6950,
    "adjustment_label": "مبادرة لك ان تشارك", "adjustment_value": "-1500",
    "client_business_name": "ميرة سالم عبيد", "client_phone1": "0557594355",
    "Client": {"client_number": "004239"},
    "InvoiceItem": [
        {"item": "WATER COOLER 2 WOLF BLACK", "description": "2-Wolf water cooler, durable and practical",
         "unit_price": "1500", "quantity": "2", "display_order": 1},
        {"item": "Saqya Al Khair – Sabeel Water Cooler jumbo", "description": "Modern Sabeel water cooler",
         "unit_price": "2500", "quantity": "1", "display_order": 0},
        {"item": "R3 – 3-Stage Filter", "unit_price": "650", "quantity": "2", "display_order": 2},
        {"item": "exchange contract", "description": "Change the filter candles for a year\r\n",
         "unit_price": "1200", "quantity": "1", "display_order": 3},
        {"item": "Electricity Connection Service", "unit_price": "150", "quantity": "1", "display_order": 4},
        {"item": "Water Connection Service", "unit_price": "150", "quantity": "1", "display_order": 5},
        {"item": "BLACK CERAMIC", "unit_price": "150", "quantity": "1", "display_order": 6},
    ],
    "InvoiceTax": {"3": {"name": "VAT Included", "value": "5.0000", "invoice_value": 402.3809523809525,
                         "included": "1"}},
    "notes": "طريقة الدفع: تحويل بنكي\nملاحظات: براده سقيا الخير المدمجه\n",
    "html_notes": "<p><b>شروط وأحكام الضمان</b></p><p><b><br></b></p><p><b>1. يقرّ العميل &amp; يوافق.</b></p>"
                  "<p><b><br></b></p><p><b><br></b></p><p><b>2. <img src=\"http://x\">الضمان سنة.</b></p>",
}


def request(**data):
    return SimpleNamespace(
        data={"customer_name": "ميرة  سالم عبيد", "phone": "0557594355", "emirate": "رأس الخيمة",
              "area": "الظيت الجنوبي", "street": "31A", "house": "67", **data},
        daftra_estimate_no="00347",
        created_by=SimpleNamespace(daftra_staff_id=None, full_name="محمد", username="m"))


def drawn(monkeypatch, estimate=ESTIMATE, **data) -> dict:
    """What draw_estimate hands the template."""
    seen = {}
    monkeypatch.setattr(printouts, "estimate", lambda **values: seen.update(values) or b"%PDF")
    draw_estimate(request(**data), estimate)
    return seen


def test_the_lines_and_the_amounts_are_daftras_own(monkeypatch, fake_daftra):
    values = drawn(monkeypatch)
    assert [line["name"] for line in values["lines"]] == [
        "Saqya Al Khair – Sabeel Water Cooler jumbo", "WATER COOLER 2 WOLF BLACK", "R3 – 3-Stage Filter",
        "exchange contract", "Electricity Connection Service", "Water Connection Service", "BLACK CERAMIC"]
    second = values["lines"][1]
    assert (second["unit_price"], second["quantity"], second["total"]) == ("1,500.00", "2", "3,000.00")
    assert values["lines"][3]["description"] == "Change the filter candles for a year"
    # English starting with a digit still reads left to right: «2-Wolf …», not «… practical-2»
    assert values["lines"][1]["description_ltr"] and values["lines"][1]["name_ltr"]
    assert values["subtotal"] == "8,450.00"
    assert (values["adjustment_label"], values["adjustment"]) == ("مبادرة لك ان تشارك", "-1,500.00")
    assert values["total"] == "6,950.00"
    assert values["taxes"] == [{"label": "شامل ضريبة القيمة المضافة 5%", "amount": "402.38",
                                "included": True}]


def test_the_header_is_the_estimates_and_the_requests(monkeypatch, fake_daftra):
    values = drawn(monkeypatch)
    assert (values["number"], values["date"]) == ("00347", "12/11/2026")
    assert (values["client_name"], values["client_code"], values["phone"]) == ("ميرة سالم عبيد", "004239", "0557594355")
    assert values["address"] == "رأس الخيمة، الظيت الجنوبي، 31A، 67"
    assert values["sales_person"] == "محمد"


def test_no_discount_prints_no_discount_line(monkeypatch, fake_daftra):
    values = drawn(monkeypatch, {**ESTIMATE, "adjustment_value": "0", "summary_total": 8450})
    assert values["subtotal"] == values["total"] == "8,450.00"
    assert values["adjustment"] == ""


def test_the_notes_and_the_terms_are_lines_of_text(monkeypatch, fake_daftra):
    values = drawn(monkeypatch)
    assert values["notes"] == ["طريقة الدفع: تحويل بنكي", "ملاحظات: براده سقيا الخير المدمجه"]
    # One gap however many empty paragraphs, and no HTML from Daftra reaches the PDF
    assert values["terms"] == ["شروط وأحكام الضمان", "", "1. يقرّ العميل & يوافق.", "", "2. الضمان سنة."]


def test_a_line_written_in_arabic_reads_right_to_left():
    from app.modules.invoicing.estimate import left_to_right
    assert not left_to_right("2 حنفية ابيض") and left_to_right("2-Wolf water cooler") and not left_to_right("")


def test_html_lines_keeps_a_break_inside_a_paragraph():
    assert html_lines("<p>one<br>two</p>") == ["one", "two"]
    assert html_lines("") == []


def test_the_template_prints_every_part_and_escapes_what_it_is_given():
    html = printouts._env.get_template("estimate.html").render(
        number="00347", date="12/11/2026", client_name="ميرة", client_code="004239", phone="0557594355",
        address="رأس الخيمة", sales_person="محمد",
        lines=[{"name": "<b>X</b>", "description": "d", "unit_price": "1,500.00", "quantity": "2",
                "total": "3,000.00"}],
        subtotal="8,450.00", adjustment_label="مبادرة", adjustment="-1,500.00", total="6,950.00",
        taxes=[{"label": "شامل ضريبة القيمة المضافة 5%", "amount": "402.38", "included": True}],
        notes=["طريقة الدفع: تحويل بنكي"], terms=["شروط", "", "1. بند"])
    for value in ("عرض سعر", "00347", "12/11/2026", "004239", "8,450.00 AED", "-1,500.00 AED", "6,950.00 AED",
                  "402.38 AED", "طريقة الدفع: تحويل بنكي", "1. بند", "&lt;b&gt;X&lt;/b&gt;"):
        assert value in html, value
    # The included VAT is printed under the total, as part of it
    assert html.index("6,950.00 AED") < html.index("402.38 AED")


def test_it_comes_out_as_a_pdf(fake_daftra):
    """The real engine, as the backend image has it."""
    content = draw_estimate(request(), ESTIMATE)
    assert content.startswith(b"%PDF")
