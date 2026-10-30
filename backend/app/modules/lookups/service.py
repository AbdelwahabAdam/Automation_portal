"""Daftra's own lists, as the forms offer them."""

from ...core.errors import ExternalFailure
from ...integrations import daftra


def from_daftra(load, failure: str):
    """A Daftra list, or the given message when Daftra cannot be reached."""
    try:
        return load()
    except daftra.DaftraError:
        raise ExternalFailure(failure)


def staff():
    """Names only, for the forms' «staff» fields (اسم المحصل، اسم من اعتمد الخصم)."""
    return from_daftra(daftra.list_staff, "تعذر تحميل الموظفين من دفترة")


def staff_members():
    """With their ids, for a field that holds the staff member and not just their name (الفني)."""
    return from_daftra(daftra.list_staff_members, "تعذر تحميل الموظفين من دفترة")


def treasuries():
    return from_daftra(daftra.list_treasuries, "تعذر تحميل الخزائن من دفترة")


def order_sources():
    return from_daftra(daftra.list_order_sources, "تعذر تحميل مصادر الطلب من دفترة")
