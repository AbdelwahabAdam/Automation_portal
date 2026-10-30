"""Where the forms put themselves as they are imported.

`app/forms/__init__.py` imports every form folder, and each one calls `register`. Nothing keeps
a second list of forms in step: the registry is the list.
"""

from ...core import permissions
from .spec import FormSpec

_forms: dict[str, FormSpec] = {}


def register(spec: FormSpec) -> FormSpec:
    """Adds a form, and declares the three permissions made from its key.

    Two forms with one key would mean one of them was never reachable. A new form is closed to
    everyone but admins until an admin grants one of these.
    """
    if spec.key in _forms:
        raise ValueError(f"two forms are registered as {spec.key!r}")
    _forms[spec.key] = spec
    permissions.declare_form(spec.key, spec.label)
    return spec


def get(key: str) -> FormSpec:
    """The form with this key, or KeyError — a request's form_type is always one of them."""
    return _forms[key]


def find(key: str) -> FormSpec | None:
    return _forms.get(key)


def known(key: str) -> bool:
    return key in _forms


def form_fields(key: str) -> list[dict]:
    """Every field of a form, section by section."""
    return _forms[key].fields()


def all_forms() -> list[FormSpec]:
    """Every form, in the order they were registered, which is the order of النماذج."""
    return list(_forms.values())


def visible_forms() -> list[FormSpec]:
    return [spec for spec in _forms.values() if spec.visible]


def keys() -> list[str]:
    return list(_forms)


def may(user, key: str, does: str) -> bool:
    """Whether this user may do that with this form."""
    return permissions.holds(user, permissions.form_permission(key, does))


def forms_for(user, does: str) -> list[FormSpec]:
    """The forms this user may do that with, in the order of النماذج."""
    return [spec for spec in _forms.values() if may(user, spec.key, does)]


def clear():
    """For a test that registers forms of its own."""
    _forms.clear()
