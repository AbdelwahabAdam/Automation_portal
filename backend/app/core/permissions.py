"""Every permission the portal knows, and the menu built from them.

A permission is a key a role can hold. There are two kinds:

- **a form's**, three per form, made from its key — nobody writes them by hand:
  `form.<key>.submit` (fill it in and send it), `form.<key>.view` (see everyone's requests of
  it), `form.<key>.review` (decide on them, which includes seeing them).
- **an admin page's**, one each: `admin.users`, `admin.roles`, …

Modules and forms declare theirs as they are imported, so the roles screen lists them without
anyone keeping a second list in step. A new form is therefore closed to everyone but admins
until an admin grants it: its three keys simply appear in the roles screen.
"""

from dataclasses import dataclass

# Permissions nobody may put in a role, because whoever held one could grant themselves anything
ADMIN_ONLY = {"admin.users", "admin.roles"}

SUBMIT, VIEW, REVIEW = "submit", "view", "review"
# What each of a form's three permissions lets someone do, for the roles screen's three boxes
WHAT = {SUBMIT: "تعبئة", VIEW: "عرض", REVIEW: "مراجعة"}


@dataclass(frozen=True)
class Permission:
    key: str
    label: str
    #: "form" or "admin": the roles screen shows the two apart
    kind: str = "admin"
    #: For a form's permission: its form key and which of the three it is
    form: str = ""
    does: str = ""

    @property
    def assignable(self) -> bool:
        return self.key not in ADMIN_ONLY


_declared: dict[str, Permission] = {}


def declare(key: str, label: str, kind: str = "admin", form: str = "", does: str = "") -> Permission:
    """Adds a permission to the registry. Declaring the same key twice is a mistake."""
    if key in _declared and _declared[key].label != label:
        raise ValueError(f"the permission {key} is already declared as {_declared[key].label!r}")
    permission = Permission(key=key, label=label, kind=kind, form=form, does=does)
    _declared[key] = permission
    return permission


def declare_form(form_key: str, label: str) -> list[Permission]:
    """A form's three permissions. Called by the form engine as each form registers."""
    return [declare(form_permission(form_key, does), f"{WHAT[does]} — {label}",
                    kind="form", form=form_key, does=does)
            for does in (SUBMIT, VIEW, REVIEW)]


def form_permission(form_key: str, does: str) -> str:
    return f"form.{form_key}.{does}"


def all_permissions() -> list[Permission]:
    """Every declared permission, in the order it was declared."""
    return list(_declared.values())


def assignable_keys() -> list[str]:
    """The keys a role may hold, in declaration order."""
    return [p.key for p in _declared.values() if p.assignable]


def known(key: str) -> bool:
    return key in _declared


def get(key: str) -> Permission | None:
    return _declared.get(key)


def form_keys_with(does: str, keys) -> list[str]:
    """Which forms these permission keys grant `does` on."""
    held = set(keys)
    return [p.form for p in _declared.values()
            if p.kind == "form" and p.does == does and p.key in held]


def clear():
    """For a test that declares permissions of its own."""
    _declared.clear()


# ---------- Who holds what ----------


def holds(user, *keys: str) -> bool:
    """Whether the user holds at least one of these permissions. An admin holds every one."""
    if getattr(user, "is_admin", False):
        return True
    return bool(set(keys) & set(user.permissions))


def holds_any_form(user, does: str) -> bool:
    """Whether any form at all is open to this user in that way."""
    if getattr(user, "is_admin", False):
        return bool(_declared)
    return any(key.startswith("form.") and key.endswith(f".{does}") for key in user.permissions)


# ---------- The menu ----------

# One entry per screen: its key (what the frontend draws), its label, where it lives, and what a
# user must hold to see it. `any_form` means "any form at all in that way".
#
# The «المبيعات» group is «الطلبات» now: the forms are no longer sales-only, so a technician's
# النماذج would otherwise sit under المبيعات.
MENU = [
    {
        "key": "requests", "label": "الطلبات",
        "pages": [
            {"key": "forms", "label": "النماذج", "path": "/forms", "any_form": SUBMIT},
            {"key": "my_requests", "label": "طلباتي", "path": "/requests/mine", "any_form": SUBMIT,
             "or_owns_requests": True},
            {"key": "review", "label": "المراجعة", "path": "/review", "any_form": [VIEW, REVIEW]},
        ],
    },
    {
        "key": "admin", "label": "الإدارة",
        "pages": [
            {"key": "admin.users", "label": "المستخدمون", "path": "/admin/users"},
            {"key": "admin.roles", "label": "الأدوار والصلاحيات", "path": "/admin/roles"},
            {"key": "admin.audit", "label": "سجل النشاط", "path": "/admin/audit"},
            {"key": "admin.catalog", "label": "المنتجات والباقات", "path": "/admin/catalog"},
            {"key": "admin.sync", "label": "المزامنة مع دفترة", "path": "/admin/sync"},
            {"key": "admin.order_sources", "label": "مصادر الطلب", "path": "/admin/order-sources"},
            {"key": "admin.mail", "label": "اختبار البريد", "path": "/admin/mail"},
        ],
    },
]

# The admin pages, declared here because the menu is where they are named
ADMIN_PAGES = [page for group in MENU if group["key"] == "admin" for page in group["pages"]]


def declare_admin_pages():
    """Each admin page's own permission. Called once as the app starts."""
    for page in ADMIN_PAGES:
        declare(page["key"], page["label"])


def _may_open(page: dict, user, owns_requests: bool) -> bool:
    wanted = page.get("any_form")
    if wanted is not None:
        if any(holds_any_form(user, does) for does in ([wanted] if isinstance(wanted, str) else wanted)):
            return True
        # Someone who has had their access taken away still reaches their own requests
        return bool(page.get("or_owns_requests") and owns_requests)
    return holds(user, page["key"])


def navigation(user, owns_requests: bool = False) -> list[dict]:
    """The menu this user sees: the groups that have at least one page they may open."""
    tree = []
    for group in MENU:
        pages = [{"key": page["key"], "label": page["label"], "path": page["path"]}
                 for page in group["pages"] if _may_open(page, user, owns_requests)]
        if pages:
            tree.append({"key": group["key"], "label": group["label"], "pages": pages})
    return tree
