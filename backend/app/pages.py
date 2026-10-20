"""The pages of the portal, grouped by department.

A role is a list of page keys. To add a page, add it here and give it a screen
in `frontend/src/pages.jsx`; until then the frontend shows a blank page with its label.
"""

# A hidden department (and its pages) is not shown to anyone, nor offered in roles or as a department
# to manage; it stays defined so old activity-log entries still read. Remove "hidden" to bring it back.
DEPARTMENTS = [
    {"key": "sales", "label": "المبيعات"},
    {"key": "data_entry", "label": "إدخال البيانات", "hidden": True},
    {"key": "accounting", "label": "الحسابات", "hidden": True},
    {"key": "operations", "label": "أوامر الشغل والتركيبات", "hidden": True},
    {"key": "admin", "label": "الإدارة"},
]
HIDDEN_DEPARTMENTS = {d["key"] for d in DEPARTMENTS if d.get("hidden")}

# Admin pages are open to admins only and cannot be put in a role
ADMIN_DEPARTMENT = "admin"

# A page marked manager=True is for the department's managers: it cannot be put in a role.
# A manager of a department opens every page of that department.
PAGES = [
    {"key": "sales.new_request", "label": "النماذج"},
    {"key": "sales.my_requests", "label": "طلباتي"},
    {"key": "sales.review", "label": "المراجعة", "manager": True},
    {"key": "data_entry.home", "label": "إدخال البيانات"},
    {"key": "accounting.home", "label": "الحسابات"},
    {"key": "operations.home", "label": "أوامر الشغل والتركيبات"},
    {"key": "admin.users", "label": "المستخدمون"},
    {"key": "admin.permissions", "label": "الأدوار والصلاحيات"},
    {"key": "admin.audit", "label": "سجل النشاط"},
    {"key": "admin.catalog", "label": "المنتجات والباقات"},
    {"key": "admin.mail", "label": "اختبار البريد"},
]


def department_of(page_key: str) -> str:
    return page_key.split(".", 1)[0]


# The pages anyone can open: those of hidden departments are left out
ALL_PAGE_KEYS = [page["key"] for page in PAGES if department_of(page["key"]) not in HIDDEN_DEPARTMENTS]
ASSIGNABLE_PAGE_KEYS = [
    key for key in ALL_PAGE_KEYS
    if department_of(key) != ADMIN_DEPARTMENT and not next(p for p in PAGES if p["key"] == key).get("manager")
]
# Departments a user can be made manager of
MANAGEABLE_DEPARTMENTS = [d["key"] for d in DEPARTMENTS if d["key"] != ADMIN_DEPARTMENT and not d.get("hidden")]
DEPARTMENT_LABELS = {d["key"]: d["label"] for d in DEPARTMENTS}


def navigation(page_keys) -> list[dict]:
    """The departments that have at least one of the given pages, each with those pages."""
    allowed = set(page_keys)
    tree = []
    for department in DEPARTMENTS:
        pages = [page for page in PAGES if department_of(page["key"]) == department["key"] and page["key"] in allowed]
        if pages:
            tree.append({**department, "pages": pages})
    return tree
