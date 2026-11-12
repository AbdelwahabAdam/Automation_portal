"""لوحة المتابعة: what the five cards count, and what «محتاج متابعة منك» lists.

The requests are built here rather than sent through the forms, because every number on the page
is about *when* something happened and these tests need those moments exactly.
"""

from datetime import datetime

from app.core.text import UAE
from app.modules.models import Request, RequestEvent

from ...conftest import auth, make_user, may_fill

NOVEMBER = 2026, 11


def at(day: int, hour: int = 9, minute: int = 0) -> datetime:
    """A moment of a November day as the office reads it: UAE time, not UTC."""
    return datetime(*NOVEMBER, day, hour, minute, tzinfo=UAE)


def event(request, kind, when, user):
    return RequestEvent(request=request, at=when, user_id=user.id if user else None,
                        username=getattr(user, "full_name", ""), kind=kind, revision=1)


def make(db, owner, *, form_type="new_sale", status="submitted", sent=None, resent=None,
         decided=None, decided_by=None, decision="approved", reason=None, name="عميل"):
    """A request with the history that put it in the state it is in."""
    request = Request(form_type=form_type, data={"customer_name": name}, status=status, revision=1,
                      created_by_id=owner.id, submitted_at=resent or sent)
    db.add(request)
    db.flush()
    db.add(event(request, "created", sent or at(1), owner))
    if sent:
        db.add(event(request, "submitted", sent, owner))
    if decided:
        decider = decided_by or owner
        db.add(event(request, decision, decided, decider))
        request.reviewed_at = decided
        request.reviewed_by_id = decider.id
        request.returned_reason = reason
    if resent:
        db.add(event(request, "resubmitted", resent, owner))
        request.reviewed_at = None
    db.commit()
    return request


def ask(client, user, **params):
    answer = client.get("/api/dashboard", params={"from": "2026-11-01", "to": "2026-11-09", **params},
                        headers=auth(user))
    assert answer.status_code == 200, answer.json()
    return answer.json()


def cards(client, user, **params):
    return ask(client, user, **params)["cards"]


def test_the_six_cards_count_their_own_periods(client, db, sales, manager):
    # Sent and approved inside the period: counted by both
    make(db, sales, sent=at(2, 9), decided=at(2, 12), decided_by=manager, status="approved")
    # Sent before the period, approved inside it: approved only
    make(db, sales, sent=datetime(2026, 10, 30, 9, tzinfo=UAE), decided=at(3, 9), decided_by=manager,
         status="approved")
    # Still waiting on the manager
    make(db, sales, sent=at(5, 9))
    # Returned to the employee and not sent again
    make(db, sales, sent=at(4, 9), decided=at(4, 15), decided_by=manager, status="returned",
         decision="returned", reason="استكمال عنوان العميل")
    # One the employee is still writing: waiting on nobody, but not sent either
    make(db, sales, sent=None, status="draft")
    assert cards(client, manager) == {
        "submitted": 3, "approved": 2, "awaiting_review": 1, "awaiting_updates": 1, "drafts": 1,
        # Waits of 3h, 96h and 6h: the middle one. A return is a decision too.
        "review_hours": 6.0, "review_count": 3,
    }


def test_a_request_sent_again_is_still_one_submission(client, db, sales, manager):
    """Returned and sent again: one order, counted once, and waiting on the manager now."""
    make(db, sales, sent=at(2, 9), decided=at(2, 11), decided_by=manager, decision="returned",
         resent=at(6, 9), status="submitted")
    numbers = cards(client, manager)
    assert numbers["submitted"] == 1 and numbers["awaiting_review"] == 1


def test_a_backlog_older_than_the_period_is_still_shown(client, db, sales, manager):
    """The two waiting cards are about now, so they ignore the dates on purpose."""
    make(db, sales, sent=datetime(2026, 9, 1, 9, tzinfo=UAE))
    numbers = cards(client, manager)
    assert numbers["submitted"] == 0 and numbers["awaiting_review"] == 1


def test_a_request_its_own_author_decided_is_left_out_of_the_review_time(client, db, admin, manager):
    """Nobody waited on another person for it, so it says nothing about how long review takes."""
    make(db, admin, sent=at(2, 9), decided=at(2, 19), decided_by=admin, status="approved")
    numbers = cards(client, manager)
    assert numbers["approved"] == 1
    assert numbers["review_hours"] is None and numbers["review_count"] == 0


def test_the_review_time_is_the_middle_of_an_even_number_of_waits(client, db, sales, manager):
    for day, hour in ((2, 10), (3, 12), (4, 14), (5, 19)):
        make(db, sales, sent=at(day, 9), decided=at(day, hour), decided_by=manager, status="approved")
    # Waits of 1, 3, 5 and 10 hours: halfway between the two in the middle
    assert cards(client, manager)["review_hours"] == 4.0


def test_an_empty_month_counts_nothing_and_says_so(client, db, manager):
    assert cards(client, manager) == {"submitted": 0, "approved": 0, "awaiting_review": 0,
                                      "awaiting_updates": 0, "drafts": 0, "review_hours": None,
                                      "review_count": 0}


def test_the_days_belong_to_the_office_not_to_utc(client, db, sales, manager):
    """Both chosen days are inside the period, read in UAE time: half past midnight on 1 November
    and half past eleven at night on the 9th are in, the same hour of 31 October is not."""
    make(db, sales, sent=at(1, 0, 30))
    make(db, sales, sent=at(9, 23, 30))
    make(db, sales, sent=datetime(2026, 10, 31, 23, 30, tzinfo=UAE))
    assert cards(client, manager)["submitted"] == 2


def test_a_period_that_ends_before_it_begins_is_refused(client, db, manager):
    answer = client.get("/api/dashboard", params={"from": "2026-11-09", "to": "2026-11-01"},
                        headers=auth(manager))
    assert answer.status_code == 422 and "تاريخ البداية" in str(answer.json())


def test_only_the_forms_the_manager_may_decide_on_are_counted(client, db, sales):
    """عرض shows a form's requests in المراجعة but puts nothing on this page."""
    watcher = make_user(db, "watcher", permissions=["form.new_sale.view", "form.maintenance.review"])
    make(db, sales, form_type="new_sale", sent=at(2, 9))
    make(db, sales, form_type="maintenance", sent=at(3, 9))
    numbers = cards(client, watcher)
    assert numbers["submitted"] == 1 and numbers["awaiting_review"] == 1
    assert [form["key"] for form in ask(client, watcher)["forms"]] == ["maintenance"]


def test_someone_who_only_fills_forms_in_cannot_open_it(client, db, sales):
    assert client.get("/api/dashboard", headers=auth(sales)).status_code == 403


def test_the_form_filter_narrows_every_card(client, db, sales, manager):
    make(db, sales, form_type="new_sale", sent=at(2, 9))
    make(db, sales, form_type="maintenance", sent=at(3, 9), decided=at(3, 10), decided_by=manager,
         status="approved")
    numbers = cards(client, manager, form_type="maintenance")
    assert (numbers["submitted"], numbers["approved"], numbers["awaiting_review"]) == (1, 1, 0)


def test_a_form_the_manager_may_not_decide_on_is_refused_as_a_filter(client, db):
    watcher = make_user(db, "watcher2", permissions=["form.maintenance.review"])
    answer = client.get("/api/dashboard", params={"form_type": "new_sale"}, headers=auth(watcher))
    assert answer.status_code == 422


def test_the_employee_filter_is_about_the_owner_not_the_reviewer(client, db, sales, manager):
    other = make_user(db, "sales2", permissions=may_fill("new_sale"), full_name="Sales Two")
    make(db, sales, sent=at(2, 9), decided=at(2, 12), decided_by=manager, status="approved")
    make(db, other, sent=at(3, 9), decided=at(3, 12), decided_by=manager, status="approved")
    assert cards(client, manager, employee=sales.id)["approved"] == 1
    # Both employees are offered, whichever form is picked
    assert sorted(one["name"] for one in ask(client, manager)["employees"]) == ["Sales One", "Sales Two"]


def test_the_waiting_list_puts_the_longest_wait_first(client, db, sales, manager):
    make(db, sales, sent=at(7, 9), name="أحمد سالم")
    make(db, sales, sent=at(4, 9), decided=at(8, 7), decided_by=manager, status="returned",
         decision="returned", reason="استكمال عنوان العميل", name="خالد حسن")
    make(db, sales, sent=at(9, 10), name="سالم راشد")
    rows = ask(client, manager)["attention"]
    assert [row["customer_name"] for row in rows] == ["أحمد سالم", "خالد حسن", "سالم راشد"]
    returned = rows[1]
    # A returned request has been waiting since it was returned, not since it was sent
    assert returned["waiting_since"].startswith("2026-11-08")
    assert returned["status"] == "returned" and returned["returned_reason"] == "استكمال عنوان العميل"
    assert rows[0]["can_review"] is True and rows[0]["form_label"]


def test_a_manager_is_offered_a_look_at_their_own_request_not_a_decision(client, db, manager):
    make(db, manager, sent=at(7, 9))
    [row] = ask(client, manager)["attention"]
    assert row["can_review"] is False


def test_the_waiting_list_follows_the_filters_but_not_the_dates(client, db, sales, manager):
    other = make_user(db, "sales3", permissions=may_fill("new_sale"), full_name="Sales Three")
    make(db, sales, sent=datetime(2026, 8, 1, 9, tzinfo=UAE), name="قديم")
    make(db, other, sent=at(7, 9), name="آخر")
    rows = ask(client, manager, employee=sales.id)["attention"]
    assert [row["customer_name"] for row in rows] == ["قديم"]


def test_the_page_says_which_moment_it_is_of(client, db, manager):
    answer = ask(client, manager)
    assert answer["refreshed_at"] and answer["from"] == "2026-11-01" and answer["to"] == "2026-11-09"


def test_without_dates_it_reads_the_month_so_far(client, db, manager):
    answer = client.get("/api/dashboard", headers=auth(manager)).json()
    today = datetime.now(UAE).date()
    assert answer["from"] == today.replace(day=1).isoformat() and answer["to"] == today.isoformat()


# ---------- The lists the cards open ----------
#
# A card links to المراجعة with the period and the basis it counted on, so the screen must be able
# to pick out the same requests. These tests pin the two to each other.


def queue(client, user, **params):
    answer = client.get("/api/review/requests", params=params, headers=auth(user))
    assert answer.status_code == 200, answer.json()
    return answer.json()


def within(moment: str | None, first="2026-11-01", last="2026-11-09") -> bool:
    """As the screen reads a moment: the UAE day it falls on, inside the chosen days."""
    if not moment:
        return False
    day = datetime.fromisoformat(moment).astimezone(UAE).date().isoformat()
    return first <= day <= last


def test_the_review_screen_can_pick_out_exactly_what_each_card_counted(client, db, sales, manager):
    make(db, sales, sent=at(2, 9), decided=at(2, 12), decided_by=manager, status="approved")
    make(db, sales, sent=datetime(2026, 10, 30, 9, tzinfo=UAE), decided=at(3, 9), decided_by=manager,
         status="approved")
    make(db, sales, sent=at(4, 9), decided=at(4, 15), decided_by=manager, decision="returned",
         resent=at(6, 9), status="submitted")
    make(db, sales, sent=at(5, 9))
    # Decided by its own author: counted as approved, left out of زمن المراجعة
    make(db, manager, sent=at(7, 9), decided=at(7, 10), decided_by=manager, status="approved")

    numbers = cards(client, manager)
    rows = queue(client, manager, scope="review")
    sent_in_period = [row for row in rows if within(row["first_submitted_at"])]
    approved_in_period = [row for row in rows if row["status"] == "approved" and within(row["reviewed_at"])]
    decided_in_period = [row for row in rows
                         if within(row["first_decision_at"]) and row["review_hours"] is not None]
    assert len(sent_in_period) == numbers["submitted"]
    assert len(approved_in_period) == numbers["approved"]
    assert len(decided_in_period) == numbers["review_count"]
    assert sorted(row["review_hours"] for row in decided_in_period) == [3.0, 6.0, 96.0]


def test_the_lists_opened_from_the_page_leave_out_the_forms_it_did_not_count(client, db, sales):
    """عرض puts a form in المراجعة but not on لوحة المتابعة, so a card's list must not show it."""
    watcher = make_user(db, "watcher3", permissions=["form.new_sale.view", "form.maintenance.review"])
    make(db, sales, form_type="new_sale", sent=at(2, 9))
    make(db, sales, form_type="maintenance", sent=at(3, 9))
    assert [row["form_type"] for row in queue(client, watcher, scope="review")] == ["maintenance"]
    # المراجعة itself is unchanged: both forms, as before
    assert len(queue(client, watcher)) == 2


def test_a_request_nobody_has_decided_on_has_no_review_time(client, db, sales, manager):
    make(db, sales, sent=at(5, 9))
    [row] = queue(client, manager, scope="review")
    assert row["first_decision_at"] is None and row["review_hours"] is None
    assert within(row["first_submitted_at"])


# ---------- The shape of the period ----------


def test_the_trend_gives_every_day_of_the_period_including_the_empty_ones(client, db, sales, manager):
    make(db, sales, sent=at(2, 9), decided=at(3, 12), decided_by=manager, status="approved")
    make(db, sales, sent=at(2, 14))
    trend = ask(client, manager)["trend"]
    assert len(trend) == 9 and trend[0]["day"] == "2026-11-01" and trend[-1]["day"] == "2026-11-09"
    by_day = {row["day"]: (row["submitted"], row["approved"]) for row in trend}
    assert by_day["2026-11-01"] == (0, 0)
    assert by_day["2026-11-02"] == (2, 0)
    # Approved the next day, so it is counted on the day it was approved
    assert by_day["2026-11-03"] == (0, 1)


def test_a_day_is_the_office_s_day_in_the_trend_too(client, db, sales, manager):
    """Half past eleven at night here is still that day, though in UTC it is the next."""
    make(db, sales, sent=at(4, 23, 30))
    by_day = {row["day"]: row["submitted"] for row in ask(client, manager)["trend"]}
    assert by_day["2026-11-04"] == 1 and by_day["2026-11-05"] == 0


def test_the_split_by_form_puts_the_busiest_first(client, db, sales, manager):
    for _ in range(3):
        make(db, sales, form_type="maintenance", sent=at(2, 9))
    make(db, sales, form_type="new_sale", sent=at(3, 9), decided=at(3, 12), decided_by=manager,
         status="approved")
    rows = ask(client, manager)["by_form"]
    assert [(row["key"], row["submitted"], row["approved"]) for row in rows] == [
        ("maintenance", 3, 0), ("new_sale", 1, 1)]
    assert rows[0]["label"] and rows[0]["label"] != "maintenance"


def test_a_form_with_nothing_in_the_period_is_left_out_of_the_split(client, db, sales, manager):
    make(db, sales, form_type="new_sale", sent=datetime(2026, 10, 1, 9, tzinfo=UAE))
    assert ask(client, manager)["by_form"] == []


def test_the_period_before_is_the_same_length_ending_the_day_before(client, db, sales, manager):
    answer = ask(client, manager)
    # 1–9 November is nine days, so the nine days before it are 23–31 October
    assert (answer["before"]["from"], answer["before"]["to"]) == ("2026-10-23", "2026-10-31")


def test_the_period_before_is_counted_the_same_way(client, db, sales, manager):
    make(db, sales, sent=at(2, 9), decided=at(2, 12), decided_by=manager, status="approved")
    make(db, sales, sent=datetime(2026, 10, 25, 9, tzinfo=UAE),
         decided=datetime(2026, 10, 25, 15, tzinfo=UAE), decided_by=manager, status="approved")
    answer = ask(client, manager)
    assert (answer["cards"]["submitted"], answer["cards"]["approved"]) == (1, 1)
    assert (answer["before"]["submitted"], answer["before"]["approved"]) == (1, 1)
    # Three hours against six: the page can say the review got faster
    assert (answer["cards"]["review_hours"], answer["before"]["review_hours"]) == (3.0, 6.0)


def test_the_trend_follows_the_filters(client, db, sales, manager):
    other = make_user(db, "sales4", permissions=may_fill("new_sale"), full_name="Sales Four")
    make(db, sales, sent=at(2, 9))
    make(db, other, sent=at(2, 10))
    by_day = {row["day"]: row["submitted"] for row in ask(client, manager, employee=sales.id)["trend"]}
    assert by_day["2026-11-02"] == 1


def test_a_period_too_long_to_draw_is_left_undrawn(client, db, manager):
    answer = client.get("/api/dashboard", params={"from": "2024-01-01", "to": "2026-11-09"},
                        headers=auth(manager))
    assert answer.status_code == 200
    # The cards still count it; the line would be hundreds of points nobody can read
    assert answer.json()["trend"] == [] and answer.json()["cards"]["submitted"] == 0


def test_the_waiting_list_can_be_read_the_other_way_round(client, db, sales, manager):
    """الأحدث في الانتظار: what has just come in, for a manager looking at the new rather than the late."""
    make(db, sales, sent=at(7, 9), name="أحمد سالم")
    make(db, sales, sent=at(9, 10), name="سالم راشد")
    assert [row["customer_name"] for row in ask(client, manager, sort="newest")["attention"]] == [
        "سالم راشد", "أحمد سالم"]
    assert ask(client, manager, sort="newest")["sort"] == "newest"
    # The default is the work that has waited longest
    assert [row["customer_name"] for row in ask(client, manager)["attention"]] == ["أحمد سالم", "سالم راشد"]


def test_an_order_the_page_does_not_know_is_refused(client, db, manager):
    answer = client.get("/api/dashboard", params={"sort": "whatever"}, headers=auth(manager))
    assert answer.status_code == 422
