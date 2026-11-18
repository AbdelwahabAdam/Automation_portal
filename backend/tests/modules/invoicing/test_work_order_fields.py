"""The work order's fields that are lists in Daftra: a value that is not one of a list's entries to
the letter is emptied the next time anyone saves the work order in Daftra's own screens."""

from app.modules.form_engine import INSCRIPTIONS
from app.modules.form_engine.options import PACKAGE_COLOR_FAMILIES
import pytest

from app.core.config import settings
from app.modules.invoicing.work_order import (COOLER_ENTRIES, INSCRIPTION_ENTRIES, PLATE_ENTRIES, STAINLESS_ENTRY,
                                              listed_values, work_order_status)

# The entries of Daftra's lists, as the account's own form shows them
PLATE_LIST = {"اللون الابيض", "اللون الاسود", "اللون الدهبي", "اللون الخشبي", "اللون العيناوي", "اللون الازرق"}
COOLER_LIST = {"اللون الابيض ", "اللون الاسود ", "اللون الدهبي ", STAINLESS_ENTRY}
NABAA = "باقة برادة نبع المزن - 3 صنابير - أسود"
VERSE = next(text for code, text in INSCRIPTIONS if code == "001")


def line(name=NABAA, group="g1", **details):
    return {"name": "part", "group_id": group, "group_name": name if group else "", "details": details}


def test_a_package_with_a_spare_part_fills_the_lists_from_the_package():
    """Work order 3252: a cooler and a tap. The tap's «أخرى» was joined into the cooler's colours,
    and five fields were emptied by the next save in Daftra."""
    data = {"order_lines": [
        line(cooler_color="أسود", cover_color="الأبيض *  اللون الاسود", inscription=VERSE, cover_back="باب W مفصلي"),
        line(cooler_color="أسود", cover_color="الأبيض *  اللون الاسود", inscription=VERSE),
        {"name": 'Bib Cock "1/2', "group_id": None, "details": {"cooler_color": "أخرى", "inscription": "لا يوجد"}},
    ]}
    listed = listed_values(data, {"available_colors": "ignored"})
    assert listed["available_colors"] == "نبع المزن – اللون الأبيض *  اللون الاسود"
    assert listed["cooler_color"] == "اللون الاسود "
    assert listed["plate_color"] == "اللون الاسود"
    assert listed["inscription"] == f"001 - {VERSE}"
    assert listed["cover_back"] == "باب W مفصلي"


def test_two_packages_give_the_first_ones_values_not_both_joined():
    data = {"order_lines": [line(cooler_color="أبيض", cover_color="البني والأبيض"),
                            line(group="g2", cooler_color="ذهبي", cover_color="البني والأسود")]}
    listed = listed_values(data, {})
    assert (listed["cooler_color"], listed["plate_color"]) == ("اللون الابيض ", "اللون الابيض")


def test_a_package_comes_before_a_product_listed_ahead_of_it():
    data = {"order_lines": [{"name": "Bib Cock", "group_id": None, "details": {"cooler_color": "أخرى"}},
                            line(cooler_color="أبيض")]}
    assert listed_values(data, {})["cooler_color"] == "اللون الابيض "


def test_a_typed_verse_and_an_unlisted_colour_stay_empty_rather_than_be_wiped():
    data = {"order_lines": [line(cooler_color="أخرى", cover_color="غير معروف", inscription="نص مكتوب باليد")]}
    listed = listed_values(data, {})
    assert (listed["cooler_color"], listed["plate_color"], listed["inscription"]) == ("", "", "")


def test_a_stainless_cooler_is_listed_as_such():
    data = {"order_lines": [line(name="براد سبيل ستانلس ستيل - 3 صنابير", cooler_color="أخرى")]}
    assert listed_values(data, {})["cooler_color"] == STAINLESS_ENTRY


def test_an_order_with_nothing_in_it_lists_nothing():
    assert set(listed_values({}, {}).values()) == {""}


def test_every_cover_colour_on_the_form_has_a_plate_on_the_list():
    colors = {shown for family in PACKAGE_COLOR_FAMILIES for shown, _ in family["colors"]}
    assert colors == set(PLATE_ENTRIES)
    assert set(PLATE_ENTRIES.values()) <= PLATE_LIST


def test_every_cooler_colour_is_an_entry_of_the_list():
    assert set(COOLER_ENTRIES.values()) | {STAINLESS_ENTRY} <= COOLER_LIST


def test_verses_are_written_as_the_list_writes_them():
    """As saved on the account: «001 - …», and «104- …» from 100 on."""
    code_of = {text: code for code, text in INSCRIPTIONS}
    for text, entry in INSCRIPTION_ENTRIES.items():
        code = code_of[text]
        assert entry == (f"{code}- {text}" if int(code) >= 100 else f"{code} - {text}")


def test_a_food_cooler_in_black_on_brown_gets_a_black_plate_and_its_colours_in_words():
    """حفظ الطعام's own cover colour. Daftra's الجهاز المطلوب list has no entry for these covers, so
    the work order says it in words, as it did before; لون اللوحه is the list's black."""
    food = "باقة برادة حفظ الطعام - غطاء نبع المزن"
    listed = listed_values({"order_lines": [line(food, cover_color="اسود في بني")]},
                           {"available_colors": "باقة برادة حفظ الطعام - غطاء نبع المزن – لون الغطاء اسود في بني"})
    assert listed["plate_color"] == "اللون الاسود" and listed["plate_color"] in PLATE_LIST
    assert listed["available_colors"] == "باقة برادة حفظ الطعام - غطاء نبع المزن – لون الغطاء اسود في بني"
    # A plain colour on one is its own plate
    assert listed_values({"order_lines": [line(food, cover_color="اللون الخشبي")]}, {})["plate_color"] == "اللون الخشبي"


def test_an_order_with_a_back_door_starts_its_work_order_in_the_doors_status():
    doors = settings.daftra_work_order_door_status_id
    assert doors == 107   # «ابواب» on our account
    for name in ("باب خلفي جرار لبرادة مدمجة", "باب خلفي مفصلي لبرادة 3 صنابير",
                 "باب خلفي مفصلي لبرادة 4 صنابير", "باب خلفي مفصلي لبرادة خاصة (Special)"):
        assert work_order_status({"order_lines": [line(name)]}) == doors, name
    # With a cooler beside it the order still has a door in it
    assert work_order_status({"order_lines": [line(NABAA), line("باب خلفي جرار لبرادة مدمجة", group="g2")]}) == doors
    # A door picked on its own, not as a package, is still a door
    assert work_order_status({"order_lines": [{"name": "باب خلفي جرار لبرادة مدمجة", "group_id": None}]}) == doors
    # Anything else starts where Daftra starts it: a cooler, a fixed panel (no door), nothing at all
    for data in ({"order_lines": [line(NABAA)]}, {"order_lines": [line("لوح خلفي ثابت لبرادة مدمجة")]}, {}):
        assert work_order_status(data) is None


@pytest.mark.parametrize("emirate, status", [("أبوظبي", 5), ("العين", 2), ("دبي", 6), ("رأس الخيمة", 187)])
def test_a_cooler_order_starts_in_its_emirates_status(emirate, status):
    for name in (NABAA, "باقة برادة سقيا الخير - 3 صنابير - أبيض", "باقة نبع المزن مدمجه - برادة مياه 3 صنابير وبرادة طعام - أبيض"):
        assert work_order_status({"emirate": emirate, "order_lines": [line(name)]}) == status, (emirate, name)


def test_a_cooler_in_an_emirate_with_no_status_of_its_own_starts_where_daftra_starts_it():
    for emirate in ("الشارقة", "عجمان", "أم القيوين", "الفجيرة", "", None):
        assert work_order_status({"emirate": emirate, "order_lines": [line(NABAA)]}) is None, emirate


def test_a_door_beats_a_cooler_and_nothing_else_is_a_cooler():
    doors = settings.daftra_work_order_door_status_id
    # A door in the order puts it in «ابواب», wherever it is
    assert work_order_status({"emirate": "دبي", "order_lines": [line(NABAA), line("باب خلفي جرار لبرادة مدمجة", group="g2")]}) == doors
    # Stainless (even named «سقيا الخير ستانلس ستيل», as the import named it), filters, a panel: none
    for name in ("باقة برادة سقيا الخير ستانلس ستيل - 3 صنابير", "باقة برادة ستانلس ستيل - 3 صنابير",
                 "باقة جهاز تنقية RO VIB - سعة 100 GPD", "لوح خلفي ثابت لبرادة مدمجة"):
        assert work_order_status({"emirate": "دبي", "order_lines": [line(name)]}) is None, name


def test_a_food_cooler_starts_in_its_own_status_whatever_its_cover_and_emirate():
    food = settings.daftra_work_order_food_cooler_status_id
    assert food == 198   # «برادة طعام بكفر نبع المزن»
    for name in ("باقة برادة حفظ الطعام - غطاء سقيا الخير", "باقة برادة حفظ الطعام - غطاء نبع المزن"):
        for emirate in ("أبوظبي", "العين", "دبي", "رأس الخيمة", "الشارقة", None):
            assert work_order_status({"emirate": emirate, "order_lines": [line(name)]}) == food, (name, emirate)
    # A combined cooler has a food cooler in it, but is not one of these: its emirate's, as before
    combined = "باقة نبع المزن مدمجه - برادة مياه 3 صنابير وبرادة طعام - أبيض"
    assert work_order_status({"emirate": "دبي", "order_lines": [line(combined)]}) == 6
    # Beside a water cooler it is still a food cooler order; beside a door, the door decides
    assert work_order_status({"emirate": "دبي", "order_lines": [line(NABAA), line("باقة برادة حفظ الطعام - غطاء نبع المزن", group="g2")]}) == food
    assert work_order_status({"emirate": "دبي", "order_lines": [line("باقة برادة حفظ الطعام - غطاء نبع المزن"),
                                                               line("باب خلفي جرار لبرادة مدمجة", group="g2")]}) == settings.daftra_work_order_door_status_id
