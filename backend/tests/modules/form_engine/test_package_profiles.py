"""Which line fields each package asks for (options.PACKAGE_PROFILES).

Named as the catalogue names them: the profiles match on the package's name, so these are the real
names from the live catalogue, not made-up ones.
"""

from app.modules.form_engine import (PACKAGE_PROFILES, form_fields, package_colors, package_fields, package_profile,
                                     validate_submission)

from ...seed import LISTS, PACKAGE_PRICES, PRODUCTS, new_sale, package_lines

FILES = {"payment_proof": 1, "design_image": 1}

NABA = "باقة برادة نبع المزن - 3 صنابير - أبيض"
NABA_COMBINED = "باقة نبع المزن مدمجه - برادة مياه 3 صنابير وبرادة طعام - أبيض"
SUQYA = "باقة برادة سقيا الخير - 3 صنابير - أسود"
SUQYA_COMBINED = "باقة سقيا الخير مدمجه - برادة مياه 3 صنابير وبرادة طعام - أبيض"
FOOD_SUQYA = "باقة برادة حفظ الطعام - غطاء سقيا الخير"
FOOD_NABA = "باقة برادة حفظ الطعام - غطاء نبع المزن"
DOORS = ["باب خلفي جرار لبرادة مدمجة", "باب خلفي مفصلي لبرادة 3 صنابير",
         "باب خلفي مفصلي لبرادة 4 صنابير", "باب خلفي مفصلي لبرادة خاصة (Special)"]
PANELS = ["لوح خلفي ثابت لبرادة مدمجة", "لوح خلفي ثابت لبرادة 4 صنابير", "لوح كلادينج ثابت لبرادة 3 صنابير"]
SHOWER = "فلتر دش Future Life"
STAINLESS = "باقة برادة ستانلس ستيل - 3 صنابير"


def line_fields(form="new_sale"):
    return next(spec for spec in form_fields(form) if spec["type"] == "order_lines")["line_fields"]


def shown(package_name, form="new_sale"):
    return [spec["name"] for spec in package_fields(line_fields(form), package_name)]


def profile_fields(package_name):
    return (package_profile(package_name) or {}).get("fields")


def validate(lines):
    return validate_submission("new_sale", new_sale(order_lines=lines), FILES, "Sales One",
                               PRODUCTS, PACKAGE_PRICES, LISTS)


def named(package_name, **details):
    """The seed's package lines, as though picked from another package."""
    return [{**line, "group_name": package_name} for line in package_lines(**details)]


# ---------- which profile ----------

def test_each_family_of_the_catalogue_resolves_to_its_profile():
    assert "design_version" in profile_fields(NABA_COMBINED)
    assert "design_version" not in profile_fields(NABA)
    assert "front_design" in profile_fields(NABA) and "w_direction" in profile_fields(NABA)
    for name in (SUQYA, SUQYA_COMBINED, FOOD_SUQYA):
        assert "front_design" not in profile_fields(name) and "cover_back" in profile_fields(name), name
    # حفظ الطعام follows the cover it carries
    assert profile_fields(FOOD_NABA) == profile_fields(NABA)
    for door in DOORS:
        assert package_profile(door)["labels"] == {"cooler_color": "لون الباب"}, door
    assert package_profile(SHOWER)["labels"] == {"cooler_color": "اللون"}
    # Neither a fixed panel nor anything else is profiled: it keeps every field, as before
    # The stainless ones also as they were imported, «… سقيا الخير ستانلس ستيل»: still not سقيا الخير
    for name in (*PANELS, STAINLESS, "باقة برادة سقيا الخير ستانلس ستيل - 3 صنابير",
                 "باقة جهاز تنقية RO VIB - سعة 100 GPD"):
        assert package_profile(name) is None, name


def test_spacing_in_a_name_does_not_change_its_profile():
    assert package_profile("  باب  خلفي   مفصلي لبرادة 3 صنابير ") is package_profile(DOORS[1])


# ---------- which fields ----------

def test_naba_shows_every_cooler_field_and_only_the_combined_ones_ask_old_or_new():
    combined, plain = shown(NABA_COMBINED), shown(NABA)
    for name in ("cooler_color", "cover_color", "plate_color", "base_color", "front_design", "w_direction",
                 "cover_back", "inscription", "manufacturing_notes", "installation_accessories"):
        assert name in combined and name in plain, name
    assert "design_version" in combined and "design_version" not in plain


def test_suqya_has_no_front_design_w_direction_or_design_version():
    fields = shown(SUQYA)
    for name in ("front_design", "w_direction", "design_version"):
        assert name not in fields, name
    for name in ("cooler_color", "cover_color", "plate_color", "base_color", "cover_back", "inscription",
                 "manufacturing_notes", "installation_accessories"):
        assert name in fields, name


def test_the_inscription_price_goes_wherever_the_inscription_goes():
    assert "inscription_price" in shown(SUQYA) and "inscription_price" in shown(NABA)
    assert "inscription_price" not in shown(DOORS[0]) and "inscription_price" not in shown(SHOWER)


def test_the_package_quantity_and_the_open_price_pair_are_on_every_package():
    for name in (SUQYA, DOORS[0], SHOWER):
        for structural in ("package_quantity", "item_price", "work_description"):
            assert structural in shown(name), (name, structural)


def test_a_door_asks_its_colour_as_door_colour_its_w_direction_and_notes_only():
    fields = package_fields(line_fields(), DOORS[3])
    own = [spec["name"] for spec in fields if not (spec.get("package_only") or spec.get("open_price_only"))]
    assert own == ["cooler_color", "w_direction", "manufacturing_notes"]
    colour = next(spec for spec in fields if spec["name"] == "cooler_color")
    # The same choices as لون البرادة, under its own name
    original = next(spec for spec in line_fields() if spec["name"] == "cooler_color")
    assert colour["label"] == "لون الباب" and colour["options"] == original["options"]


def test_the_shower_filter_asks_one_colour_of_two():
    fields = package_fields(line_fields(), SHOWER)
    own = [spec for spec in fields if not (spec.get("package_only") or spec.get("open_price_only"))]
    assert [spec["name"] for spec in own] == ["cooler_color"]
    # The catalogue's own spelling, so the work order turns it into Daftra's words (COLOR_TEXT)
    assert own[0]["label"] == "اللون" and own[0]["options"] == ["أبيض", "أسود"]


def test_a_package_no_profile_matches_keeps_every_field():
    assert shown(STAINLESS) == [spec["name"] for spec in line_fields()]
    assert shown(PANELS[0]) == [spec["name"] for spec in line_fields()]


def test_the_profiles_do_not_change_the_field_list_itself():
    before = [dict(spec) for spec in line_fields()]
    package_fields(line_fields(), DOORS[0])
    package_fields(line_fields(), SHOWER)
    assert line_fields() == before


def test_every_field_a_profile_names_is_a_real_line_field():
    names = {spec["name"] for spec in line_fields()}
    for profile in PACKAGE_PROFILES:
        assert set(profile["fields"]) <= names, profile["match"]
        assert set(profile.get("labels", {})) <= set(profile["fields"]), profile["match"]
        assert set(profile.get("options", {})) <= set(profile["fields"]), profile["match"]


# ---------- what the server keeps ----------

def test_a_field_the_package_does_not_ask_for_is_dropped_whatever_the_browser_sends():
    clean, errors = validate(named(SUQYA, front_design="مائل", w_direction="عرضي", design_version="تصميم جديد"))
    assert errors == {}
    for line in clean["order_lines"]:
        for name in ("front_design", "w_direction", "design_version"):
            assert name not in line["details"], name


def test_naba_keeps_what_it_asks_for():
    # A cover colour of نبع المزن's own: the seed's is سقيا الخير's, which نبع المزن refuses
    clean, errors = validate(named(NABA_COMBINED, cover_color="البني والأسود", front_design="مائل",
                                   w_direction="عرضي", design_version="تصميم جديد"))
    assert errors == {}
    details = clean["order_lines"][0]["details"]
    assert (details["front_design"], details["w_direction"], details["design_version"]) == ("مائل", "عرضي", "تصميم جديد")


def test_a_door_is_neither_asked_nor_charged_for_an_inscription():
    clean, errors = validate(named(DOORS[0], inscription="بسم الله", inscription_price="300"))
    assert errors == {}
    for line in clean["order_lines"]:
        assert "inscription" not in line["details"] and "inscription_price" not in line["details"]
    # So the subtotal carries the products alone, nothing for an inscription that is not made
    with_one = validate(named(SUQYA, inscription="بسم الله", inscription_price="300"))[0]
    assert with_one["subtotal_amount"] - clean["subtotal_amount"] == 300 * 2


def test_the_shower_filter_refuses_a_colour_it_does_not_come_in():
    _, errors = validate(named(SHOWER, cooler_color="ذهبي"))
    assert errors["order_lines"]["lines"]["0"]["cooler_color"]
    clean, ok = validate(named(SHOWER, cooler_color="أسود"))
    assert ok == {} and clean["order_lines"][0]["details"]["cooler_color"] == "أسود"


def test_a_form_whose_lines_are_not_packages_is_not_profiled():
    """الصيانة's items are maintenance products: one named like a package is not one."""
    for form in ("maintenance", "tech_extra_works"):
        spec = next(s for s in form_fields(form) if s["type"] == "order_lines")
        assert not spec.get("package_profiles"), form
    for form in ("new_sale", "online_sale", "quotation"):
        spec = next(s for s in form_fields(form) if s["type"] == "order_lines")
        assert spec["package_profiles"] == PACKAGE_PROFILES, form


# ---------- the combined سقيا الخير colours ----------

def test_combined_suqya_offers_its_own_cover_colours_whichever_way_مدمجة_is_spelled():
    """The live catalogue writes «مدمجه», the import wrote «مدمجة»: both are the combined family,
    whose colours are the work order's own «سقيا الخير مدمجه - …» entries."""
    plain = [shown for shown, _ in package_colors(SUQYA)]
    for name in (SUQYA_COMBINED, SUQYA_COMBINED.replace("مدمجه", "مدمجة"),
                 "باقة سقيا الخير مدمجه سبيشيال - 2 برادة مياه 3 صنابير وبرادة طعام - أبيض"):
        colours = package_colors(name)
        assert [shown for shown, _ in colours] == ["الابيض", "الاسود", "الابيض * الابيض", "الابيض * الذهبى"], name
        assert all(written.startswith("سقيا الخير مدمجه") for _, written in colours), name
        assert not set(shown for shown, _ in colours) & set(plain), name
    # The plain ones keep theirs
    assert len(plain) == 6 and "الابيض * خشابي مقاس طبيعي" in plain


def test_a_combined_suqya_line_takes_a_combined_colour_and_refuses_a_plain_one():
    clean, errors = validate(named(SUQYA_COMBINED, cover_color="الابيض * الذهبى"))
    assert errors == {} and clean["order_lines"][0]["details"]["cover_color"] == "الابيض * الذهبى"
    _, refused = validate(named(SUQYA_COMBINED, cover_color="الابيض * خشابي مقاس طبيعي"))
    assert refused["order_lines"]["lines"]["0"]["cover_color"] == "اختر من القائمة"
