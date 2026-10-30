"""Access per form: one test per rule of final_plan.md §6, and the migration that carried
today's access across.

The rules, in words:
  - a technician holding only one form sees only that form, and cannot open another by URL or API;
  - a reviewer of one form does not see another's requests;
  - view without review cannot decide;
  - a new form is closed until granted;
  - an owner still reads their request after losing submit;
  - no one but an admin decides on their own request.
"""

import pytest

from app.core import permissions
from app.modules.form_engine import keys

from ... import seed
from ...conftest import VISIBLE_FORMS, auth, make_user, may_fill, may_review
from ...seed import create, submitted_sale


def may_view(*form_keys):
    return [f"form.{key}.view" for key in form_keys]


# ---------- The permissions themselves ----------


def test_every_form_has_its_three_permissions():
    for key in keys():
        for does in (permissions.SUBMIT, permissions.VIEW, permissions.REVIEW):
            assert permissions.known(f"form.{key}.{does}"), f"{key}.{does} is not declared"


def test_the_two_admin_keys_nobody_may_hold_in_a_role():
    """Whoever held them could give themselves anything."""
    assert permissions.ADMIN_ONLY == {"admin.users", "admin.roles"}
    assert "admin.users" not in permissions.assignable_keys()
    assert "admin.roles" not in permissions.assignable_keys()


def test_an_admin_holds_every_permission(db):
    admin = make_user(db, "boss", admin=True)
    assert permissions.holds(admin, "form.new_sale.review", "admin.users")
    assert permissions.holds(admin, "anything.at.all")


def test_a_key_left_in_a_role_for_a_form_that_went_grants_nothing(db):
    user = make_user(db, "stale", permissions=["form.no_such_form.submit"])
    assert user.permissions == []


# ---------- Only the forms they were granted ----------


def test_a_technician_sees_only_their_own_form(client, db):
    tech = make_user(db, "tech", permissions=may_fill("tech_cash_collection"))
    shown = client.get("/api/form-types", headers=auth(tech)).json()
    assert [form["key"] for form in shown] == ["tech_cash_collection"]
    assert shown[0]["may_submit"] is True and shown[0]["may_review"] is False


def test_a_technician_cannot_open_another_form_by_api(client, db):
    tech = make_user(db, "tech", permissions=may_fill("tech_cash_collection"))
    assert create(client, tech, {}, form_type="new_sale").status_code == 403


def test_a_new_form_is_closed_until_it_is_granted(client, db):
    """Nobody but an admin sees it, however many other forms they hold."""
    sales = make_user(db, "seller", permissions=may_fill("new_sale"))
    shown = {form["key"] for form in client.get("/api/form-types", headers=auth(sales)).json()}
    assert shown == {"new_sale"}
    admin = make_user(db, "boss", admin=True)
    assert len(client.get("/api/form-types", headers=auth(admin)).json()) == len(keys())


# ---------- The review queue, form by form ----------


def test_a_reviewer_of_one_form_does_not_see_anothers_requests(client, db, sales):
    seed.catalog(db)
    sale = submitted_sale(client, db, sales)
    reviewer = make_user(db, "tech_lead", permissions=may_review("tech_cash_collection"))
    assert client.get("/api/review/requests", headers=auth(reviewer)).json() == []
    assert client.get(f"/api/requests/{sale}", headers=auth(reviewer)).status_code == 404
    assert client.post(f"/api/review/requests/{sale}/approve", json={"revision": 1},
                       headers=auth(reviewer)).status_code == 404


def test_a_reviewer_of_that_form_does_see_it(client, db, sales):
    seed.catalog(db)
    sale = submitted_sale(client, db, sales)
    reviewer = make_user(db, "sales_lead", permissions=may_review("new_sale"))
    queue = client.get("/api/review/requests", headers=auth(reviewer)).json()
    assert [row["id"] for row in queue] == [sale]
    assert queue[0]["can_review"] is True


def test_view_without_review_can_look_but_not_decide(client, db, sales):
    seed.catalog(db)
    sale = submitted_sale(client, db, sales)
    watcher = make_user(db, "watcher", permissions=may_view("new_sale"))
    queue = client.get("/api/review/requests", headers=auth(watcher)).json()
    assert [row["id"] for row in queue] == [sale]
    assert queue[0]["can_review"] is False
    assert client.get(f"/api/requests/{sale}", headers=auth(watcher)).status_code == 200
    # Looking is allowed; deciding is not, and says so the same way a missing request does
    assert client.post(f"/api/review/requests/{sale}/approve", json={"revision": 1},
                       headers=auth(watcher)).status_code == 404
    assert client.post(f"/api/review/requests/{sale}/return", json={"revision": 1, "reason": "صحّح الرقم"},
                       headers=auth(watcher)).status_code == 404


def test_opening_the_review_screen_at_all_takes_view_or_review(client, db):
    outsider = make_user(db, "outsider", permissions=may_fill("new_sale"))
    assert client.get("/api/review/requests", headers=auth(outsider)).status_code == 403


# ---------- The owner ----------


def test_an_owner_still_reads_their_request_after_losing_the_form(client, db, sales):
    """Their access was taken away; the request is still theirs to look at."""
    request_id = create(client, sales, {"customer_name": "x"}).json()["id"]
    sales.roles[0].permissions = []
    db.commit()
    assert client.get(f"/api/requests/{request_id}", headers=auth(sales)).status_code == 200
    assert [row["id"] for row in client.get("/api/requests/mine", headers=auth(sales)).json()] == [request_id]
    # But changing it needs the form
    assert client.put(f"/api/requests/{request_id}", json={"data": {}, "action": "draft"},
                      headers=auth(sales)).status_code == 403
    assert client.delete(f"/api/requests/{request_id}", headers=auth(sales)).status_code == 403


def test_the_menu_still_offers_their_requests_to_an_owner_who_lost_everything(client, db, sales):
    create(client, sales, {"customer_name": "x"})
    sales.roles[0].permissions = []
    db.commit()
    menu = client.get("/api/auth/me", headers=auth(sales)).json()["navigation"]
    pages = [page["key"] for group in menu for page in group["pages"]]
    assert pages == ["my_requests"]


# ---------- Deciding on your own ----------


def test_no_one_but_an_admin_decides_on_their_own_request(client, db, admin):
    seed.catalog(db)
    both = make_user(db, "player_coach",
                     permissions=may_review(*VISIBLE_FORMS) + may_fill(*VISIBLE_FORMS), daftra_staff_id=71)
    own = submitted_sale(client, db, both)
    assert client.post(f"/api/review/requests/{own}/approve", json={"revision": 1},
                       headers=auth(both)).status_code == 403
    assert client.post(f"/api/review/requests/{own}/approve", json={"revision": 1},
                       headers=auth(admin)).status_code == 200


# ---------- The admin pages ----------


@pytest.mark.parametrize("key, path", [
    ("admin.audit", "/api/admin/audit/options"),
    ("admin.catalog", "/api/admin/products"),
    ("admin.mail", "/api/admin/mail"),
    ("admin.order_sources", "/api/admin/order-sources"),
    ("admin.sync", "/api/admin/daftra-sync"),
])
def test_an_admin_page_can_be_held_without_being_an_admin(client, db, key, path):
    keeper = make_user(db, "keeper", permissions=[key])
    assert client.get(path, headers=auth(keeper)).status_code != 403
    someone_else = make_user(db, "nobody", permissions=may_fill("new_sale"))
    assert client.get(path, headers=auth(someone_else)).status_code == 403


def test_users_and_roles_stay_admin_only(client, db):
    """Whoever could edit them could grant themselves anything, so no role may hold them."""
    tried = make_user(db, "tried", permissions=["admin.users", "admin.roles"])
    assert tried.permissions == []
    assert client.get("/api/admin/users", headers=auth(tried)).status_code == 403
    assert client.get("/api/admin/roles", headers=auth(tried)).status_code == 403
