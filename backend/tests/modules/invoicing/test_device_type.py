"""نوع الجهاز («اسم الجهاز» on the client in Daftra), from the packages ordered (runner.device_type).

The names are the live catalogue's, and the local one's where it spells them otherwise.
"""

import pytest

from app.core.config import settings
from app.modules.clients.in_daftra import custom_fields
from app.modules.invoicing import device_type


def ordered(*names):
    """An order of these packages, as the form saves it: each package's lines carry its name."""
    return {"order_lines": [{"product_id": str(i), "name": "some product", "group_id": f"g{i}", "group_name": name}
                            for i, name in enumerate(names)]}


@pytest.mark.parametrize("package, expected", [
    ("باقة برادة نبع المزن - 3 صنابير - أبيض", "N"),
    ("باقة برادة سقيا الخير - 3 صنابير - أسود", "S"),
    # A combined cooler carries a food cooler of its own («… وبرادة طعام»), in either spelling
    ("باقة نبع المزن مدمجه - برادة مياه 3 صنابير وبرادة طعام - أبيض", "N + F"),
    ("باقة نبع المزن مدمجة - برادة مياه 3 صنابير وبرادة طعام - أبيض", "N + F"),
    ("باقة سقيا الخير مدمجه سبيشيال - 2 برادة مياه 3 صنابير وبرادة طعام - أسود", "S + F"),
    ("باقة برادة حفظ الطعام - غطاء نبع المزن", "N + F"),
    ("باقة برادة حفظ الطعام - غطاء سقيا الخير", "S + F"),
])
def test_each_family_gives_its_letters(package, expected):
    assert device_type(ordered(package)) == expected


@pytest.mark.parametrize("package", [
    # Made for a combined cooler, named «… مدمجة»: still no food cooler in it, and no family
    "باب خلفي جرار لبرادة مدمجة",
    "لوح خلفي ثابت لبرادة مدمجة",
    "باب خلفي مفصلي لبرادة 3 صنابير",
    # Stainless is not سقيا الخير, as the local catalogue names it nonetheless
    "باقة برادة سقيا الخير ستانلس ستيل - 3 صنابير",
    "باقة برادة ستانلس ستيل - 3 صنابير",
    "باقة جهاز تنقية RO VIB - سعة 100 GPD",
    "فلتر دش Future Life",
])
def test_a_package_of_no_family_gets_the_default(package):
    assert settings.daftra_default_device_name == "N + F"
    assert device_type(ordered(package)) == "N + F"


def test_the_letters_of_several_packages_are_written_n_s_f_once_each():
    # One order holds «N + F» at most; a mix is still written the same way, whatever was picked first
    assert device_type(ordered("باقة برادة حفظ الطعام - غطاء نبع المزن",
                               "باقة برادة نبع المزن - 3 صنابير - أبيض")) == "N + F"
    assert device_type(ordered("باب خلفي جرار لبرادة مدمجة", "باقة برادة سقيا الخير - 3 صنابير - أسود")) == "S"


def test_no_lines_at_all_gets_the_default():
    assert device_type({}) == "N + F" and device_type({"order_lines": []}) == "N + F"


def test_a_product_picked_on_its_own_is_read_by_its_own_name():
    assert device_type({"order_lines": [{"product_id": "1", "name": "باقة برادة نبع المزن - 2 صنبور - أبيض"}]}) == "N"


def test_what_the_order_says_replaces_what_the_client_held():
    """A sale sends its packages' value with every invoice; a form that sends none (تجديد عقد,
    صيانة) leaves what the client already holds."""
    held = {settings.daftra_client_device_field: "N + F", settings.daftra_client_coordinates_field: "24.1, 55.6"}
    sent = custom_fields({"device_name": "S", "coordinates": "24.1, 55.6"}, held)
    assert sent[settings.daftra_client_device_field] == "S"
    kept = custom_fields({"coordinates": "24.1, 55.6"}, held)
    assert kept[settings.daftra_client_device_field] == "N + F"
