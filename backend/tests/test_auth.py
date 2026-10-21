"""Logging in, two-step codes, password links and the account page."""

import re

from app.config import settings
from app.models import AuditLog, User
from app.security import create_password_link

from .conftest import PASSWORD, auth, make_user


def login(client, username, password=PASSWORD, code=""):
    return client.post("/api/auth/login", json={"username": username, "password": password, "code": code})


def test_login_by_username_or_email(client, sales):
    for name in ("sales1", "SALES1 ", "sales1@test.local"):
        response = login(client, name)
        assert response.status_code == 200, name
        body = response.json()
        assert body["access_token"]
        assert body["user"]["username"] == "sales1"
        assert [d["key"] for d in body["user"]["navigation"]] == ["sales"]


def test_wrong_password_is_refused_and_logged(client, db, sales):
    response = login(client, "sales1", "wrong")
    assert response.status_code == 401
    entry = db.query(AuditLog).filter_by(action="auth.login_failed").one()
    assert entry.username == "sales1"


def test_too_many_failures_lock_the_account_for_a_while(client, sales):
    for _ in range(8):
        assert login(client, "sales1", "wrong").status_code == 401
    # Even the right password waits out the window
    assert login(client, "sales1").status_code == 429


def test_inactive_and_invited_users_cannot_log_in(client, db):
    make_user(db, "stopped").is_active = False
    db.commit()
    make_user(db, "invited", password=None)
    assert login(client, "stopped").status_code == 401
    assert login(client, "invited").status_code == 401


def test_admin_logs_in_with_an_emailed_code(client, db, outbox, monkeypatch):
    monkeypatch.setattr(settings, "require_admin_mfa", True)
    make_user(db, "boss", admin=True)
    first = login(client, "boss").json()
    assert first["mfa_required"] and not first.get("access_token")
    assert first["email_hint"] == "b•••@test.local"
    code = re.search(r"\b(\d{6})\b", outbox[-1]["subject"]).group(1)
    # Asking again within the minute keeps the same code (no second email)
    login(client, "boss")
    assert len(outbox) == 1
    assert login(client, "boss", code="000000" if code != "000000" else "111111").status_code == 401
    done = login(client, "boss", code=code)
    assert done.status_code == 200 and done.json()["access_token"]
    # A code works once
    assert login(client, "boss", code=code).status_code == 401


def test_me_needs_a_valid_token(client, sales):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer nonsense"}).status_code == 401
    assert client.get("/api/auth/me", headers=auth(sales)).json()["username"] == "sales1"


def test_a_password_link_is_not_a_login_and_works_once(client, db, sales):
    token = create_password_link(sales).split("token=")[1]
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    assert client.get("/api/auth/password-link", params={"token": token}).json()["username"] == "sales1"
    assert client.post("/api/auth/set-password", json={"token": token, "password": "brand-new-pass"}).status_code == 204
    assert client.post("/api/auth/set-password", json={"token": token, "password": "another-pass"}).status_code == 400
    assert login(client, "sales1", "brand-new-pass").status_code == 200


def test_forgot_password_answers_the_same_and_sends_once_in_a_while(client, sales, outbox):
    assert client.post("/api/auth/forgot-password", json={"username": "nobody"}).status_code == 204
    assert client.post("/api/auth/forgot-password", json={"username": "sales1"}).status_code == 204
    assert client.post("/api/auth/forgot-password", json={"username": "sales1"}).status_code == 204
    assert [mail["to"] for mail in outbox] == ["sales1@test.local"]


def test_account_page(client, db, sales):
    headers = auth(sales)
    assert client.get("/api/account", headers=headers).json()["mfa_enabled"] is False
    assert client.put("/api/account", json={"full_name": "  New Name "}, headers=headers).json()["full_name"] == "New Name"
    wrong = client.post("/api/account/password", json={"current_password": "x", "new_password": "long-enough"}, headers=headers)
    assert wrong.status_code == 403
    ok = client.post("/api/account/password", json={"current_password": PASSWORD, "new_password": "long-enough"},
                     headers=headers)
    assert ok.status_code == 204
    db.expire_all()
    assert login(client, "sales1", "long-enough").status_code == 200


def test_turning_two_step_on_and_off(client, db, sales, outbox):
    headers = auth(sales)
    assert client.post("/api/account/mfa/send-code", headers=headers).status_code == 200
    code = re.search(r"\b(\d{6})\b", outbox[-1]["subject"]).group(1)
    assert client.post("/api/account/mfa/enable", json={"code": code}, headers=headers).json()["mfa_enabled"] is True
    assert login(client, "sales1").json()["mfa_required"] is True
    off = client.post("/api/account/mfa/disable", json={"password": PASSWORD}, headers=headers)
    assert off.json()["mfa_enabled"] is False
    db.expire_all()
    assert db.get(User, sales.id).mfa_enabled is False


def test_a_signed_token_without_a_user_is_no_login(client):
    import jwt

    from app.config import settings
    for payload in ({}, {"sub": "abc"}, {"sub": "999"}):
        token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
        assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
        assert client.get("/api/auth/password-link", params={"token": token}).status_code == 400
