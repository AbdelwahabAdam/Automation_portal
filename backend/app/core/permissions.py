"""Every permission the portal knows, declared by the module or form that owns it.

A permission is a key a role can hold: `form.new_sale.submit`, `admin.catalog`. Modules and
forms declare theirs as they are imported, so the roles screen lists them without anyone
keeping a second list in step. Filled in from phase 7; until then nothing declares anything.
"""

from dataclasses import dataclass

# Permissions nobody may put in a role, because whoever held one could grant themselves anything
ADMIN_ONLY = {"admin.users", "admin.roles"}


@dataclass(frozen=True)
class Permission:
    key: str
    label: str
    group: str = ""

    @property
    def assignable(self) -> bool:
        return self.key not in ADMIN_ONLY


_declared: dict[str, Permission] = {}


def declare(key: str, label: str, group: str = "") -> Permission:
    """Adds a permission to the registry. Declaring the same key twice is a mistake."""
    if key in _declared and _declared[key].label != label:
        raise ValueError(f"the permission {key} is already declared as {_declared[key].label!r}")
    permission = Permission(key=key, label=label, group=group)
    _declared[key] = permission
    return permission


def all_permissions() -> list[Permission]:
    """Every declared permission, in the order it was declared."""
    return list(_declared.values())


def assignable_keys() -> list[str]:
    """The keys a role may hold."""
    return [p.key for p in _declared.values() if p.assignable]


def known(key: str) -> bool:
    return key in _declared
