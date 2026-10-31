"""The work order's fields that are lists in Daftra: a value that is not one of a list's entries to
the letter is emptied the next time anyone saves the work order in Daftra's own screens."""

from app.modules.form_engine import INSCRIPTIONS
from app.modules.form_engine.options import PACKAGE_COLOR_FAMILIES
from app.modules.invoicing.work_order import (COOLER_ENTRIES, INSCRIPTION_ENTRIES, PLATE_ENTRIES, STAINLESS_ENTRY,
                                              listed_values)

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
