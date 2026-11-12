"""A reviewer deleting a request that is still waiting — a draft, or one sent in.

The row stays, out of sight: gone from its owner's list, from المراجعة and from every number on
لوحة المتابعة. Who deleted it, when and why are kept in its own history and in سجل النشاط, and
its owner is told by email.
"""

from app.modules.models import AuditLog, Request

from ... import seed
from ...conftest import VISIBLE_FORMS, auth, make_user, may_fill, may_review
from ...seed import create, submitted_sale

REASON = "العميل ألغى الطلب قبل التركيب، وأُعيد المبلغ."


def delete(client, user, request_id, reason=REASON):
    return client.post(f"/api/review/requests/{request_id}/delete", json={"reason": reason}, headers=auth(user))


def draft_of(client, db, sales) -> int:
    """A new sale saved and not sent."""
    seed.catalog(db)
    return create(client, sales, seed.sale_data()).json()["id"]


def sent_of(client, db, sales) -> int:
    """A new sale sent in for review, catalog and files and all."""
    seed.catalog(db)
    return submitted_sale(client, db, sales)


def test_a_reviewer_deletes_a_request_that_was_sent_in(client, db, sales, manager, outbox):
    request_id = sent_of(client, db, sales)
    response = delete(client, manager, request_id)
    assert response.status_code == 200
    assert response.json() == {"id": request_id, "status": "deleted", "email_sent": True}
    db.expire_all()
    # The row is still there, which is what makes putting it back possible
    assert db.get(Request, request_id).status == "deleted"


def test_a_draft_can_be_deleted_too(client, db, sales, manager):
    request_id = draft_of(client, db, sales)
    assert delete(client, manager, request_id).status_code == 200
    db.expire_all()
    assert db.get(Request, request_id).status == "deleted"


def test_it_leaves_the_owner_list_and_their_counts(client, db, sales, manager):
    request_id = sent_of(client, db, sales)
    assert [r["id"] for r in client.get("/api/requests/mine", headers=auth(sales)).json()] == [request_id]
    delete(client, manager, request_id)
    assert client.get("/api/requests/mine", headers=auth(sales)).json() == []
    counts = client.get("/api/requests/mine/counts", headers=auth(sales)).json()
    assert counts["submitted"] == 0 and "deleted" not in counts


def test_its_owner_can_no_longer_open_it_but_an_admin_can(client, db, sales, manager):
    request_id = sent_of(client, db, sales)
    delete(client, manager, request_id)
    assert client.get(f"/api/requests/{request_id}", headers=auth(sales)).status_code == 404
    assert client.get(f"/api/requests/{request_id}", headers=auth(manager)).status_code == 404
    admin = make_user(db, "boss", admin=True)
    assert client.get(f"/api/requests/{request_id}", headers=auth(admin)).status_code == 200


def test_it_leaves_the_review_queue(client, db, sales, manager):
    request_id = sent_of(client, db, sales)
    draft_id = create(client, sales, seed.sale_data()).json()["id"]
    delete(client, manager, request_id)
    left = [r["id"] for r in client.get("/api/review/requests", headers=auth(manager)).json()]
    assert left == [draft_id]


def test_why_it_went_is_in_its_history_and_in_the_activity_log(client, db, sales, manager):
    request_id = sent_of(client, db, sales)
    delete(client, manager, request_id)
    entry = db.query(AuditLog).filter_by(action="request.delete_by_reviewer").one()
    assert entry.after["reason"] == REASON and entry.after["status"] == "deleted"
    # What it was before, so it can be put back where it came from
    assert entry.before["status"] == "submitted" and entry.before["owner"] == sales.full_name
    assert entry.before["customer_name"] == seed.sale_data()["customer_name"]
    admin = make_user(db, "boss", admin=True)
    history = client.get(f"/api/requests/{request_id}/history", headers=auth(admin)).json()
    assert history[-1]["kind"] == "deleted" and history[-1]["note"] == REASON
    assert history[-1]["label"] == "حذف الطلب" and history[-1]["username"] == manager.full_name


def test_the_owner_is_told_by_email(client, db, sales, manager, outbox):
    request_id = sent_of(client, db, sales)
    delete(client, manager, request_id)
    [sent] = [mail for mail in outbox if "حُذف الطلب" in mail["subject"]]
    assert sent["to"] == sales.email
    assert REASON in sent["text"] and REASON in sent["html"]
    assert manager.full_name in sent["text"]


def test_an_employee_without_review_cannot_delete(client, db, sales, manager):
    request_id = sent_of(client, db, sales)
    # Its own owner may not: deleting a sent request is the reviewer's
    assert delete(client, sales, request_id).status_code == 403
    other = make_user(db, "sales2", permissions=may_fill(*VISIBLE_FORMS))
    assert delete(client, other, request_id).status_code == 403
    db.expire_all()
    assert db.get(Request, request_id).status == "submitted"


def test_a_reviewer_of_another_form_is_answered_as_though_it_were_not_there(client, db, sales):
    request_id = sent_of(client, db, sales)
    elsewhere = make_user(db, "maint", permissions=may_review("maintenance") + may_fill("maintenance"))
    assert delete(client, elsewhere, request_id).status_code == 404
    db.expire_all()
    assert db.get(Request, request_id).status == "submitted"


def test_one_returned_for_corrections_can_be_deleted(client, db, fake_daftra, sales, manager):
    """Work nobody will finish: the employee was asked to fix it and the order fell through."""
    request_id = sent_of(client, db, sales)
    assert client.post(f"/api/review/requests/{request_id}/return", json={"revision": 1, "reason": "صحّح الهاتف"},
                       headers=auth(manager)).status_code == 200
    assert delete(client, manager, request_id).status_code == 200
    db.expire_all()
    assert db.get(Request, request_id).status == "deleted"
    assert client.get("/api/requests/mine", headers=auth(sales)).json() == []


def test_an_approved_request_is_not_deleted_from_here(client, db, fake_daftra, sales, manager):
    """It has an invoice and a work order in Daftra; deleting it here would orphan them."""
    request_id = sent_of(client, db, sales)
    assert client.post(f"/api/review/requests/{request_id}/approve", json={"revision": 1},
                       headers=auth(manager)).status_code == 200
    response = delete(client, manager, request_id)
    assert response.status_code == 409 and "معتمد" in response.json()["detail"]
    db.expire_all()
    assert db.get(Request, request_id).status in ("approved", "awaiting_payment")


def test_a_reason_is_required(client, db, sales, manager):
    request_id = sent_of(client, db, sales)
    assert delete(client, manager, request_id, reason="").status_code == 422
    assert delete(client, manager, request_id, reason="  لا  ").status_code == 422
    db.expire_all()
    assert db.get(Request, request_id).status == "submitted"


def test_deleting_it_twice_is_refused(client, db, sales, manager):
    request_id = sent_of(client, db, sales)
    assert delete(client, manager, request_id).status_code == 200
    assert delete(client, manager, request_id).status_code == 404


# ---------- What لوحة المتابعة then counts ----------


def board(client, user, **params):
    query = "&".join(f"{name}={value}" for name, value in params.items())
    return client.get(f"/api/dashboard{'?' + query if query else ''}", headers=auth(user)).json()


def test_the_board_counts_the_drafts_waiting_to_be_sent(client, db, sales, manager):
    draft_of(client, db, sales)
    create(client, sales, seed.sale_data(customer_name="ثانٍ"))
    submitted_sale(client, db, sales)
    cards = board(client, manager)["cards"]
    assert cards["drafts"] == 2 and cards["awaiting_review"] == 1


def test_a_deleted_request_counts_nowhere_on_the_board(client, db, sales, manager):
    draft_id = draft_of(client, db, sales)
    sent_id = submitted_sale(client, db, sales)
    before = board(client, manager)
    assert before["cards"]["submitted"] == 1 and before["cards"]["drafts"] == 1
    delete(client, manager, draft_id)
    delete(client, manager, sent_id)
    after = board(client, manager)
    assert after["cards"] == {**after["cards"], "drafts": 0, "awaiting_review": 0, "submitted": 0}
    # And it is in no list, no chart and nobody's name in the filters
    assert after["attention"] == [] and after["employees"] == []
    assert sum(row["submitted"] for row in after["trend"]) == 0
    assert after["by_form"] == []
