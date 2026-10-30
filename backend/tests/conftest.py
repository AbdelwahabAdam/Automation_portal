"""Test setup: a separate database, Daftra replaced by tests/fake_daftra.py, email caught in a list.

Run with backend/run-tests.sh (Docker), which points DATABASE_URL at the portal_test database.
"""

import os
import socket
import urllib.request

import pytest

if "portal_test" not in os.environ.get("DATABASE_URL", ""):
    raise RuntimeError("The tests empty the database they run on: point DATABASE_URL at the portal_test database")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.modules import notifications as mail  # noqa: E402
from app.integrations import daftra  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from app.main import app  # noqa: E402
from app.modules.models import Role, User  # noqa: E402
from app.core.security import create_token, hash_password  # noqa: E402

from app.integrations.daftra.fake import FakeDaftra  # noqa: E402

PASSWORD = "secret-pass-1"


@pytest.fixture(scope="session", autouse=True)
def schema():
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public"))
    run_migrations()


@pytest.fixture(autouse=True)
def clean_tables():
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Nothing a test runs may reach Daftra, a mail server or anything else outside."""
    def refuse(*args, **kwargs):
        raise AssertionError("A test tried to reach the network")
    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


@pytest.fixture(autouse=True)
def fake_daftra(monkeypatch):
    """A Daftra account of its own per test, in memory, reached through the real switch.

    Nothing is patched over the client: `DAFTRA_FAKE` is turned on and this account put in
    place, so a test goes through the same `client.py` a local portal does.
    """
    fake = FakeDaftra()
    monkeypatch.setattr(settings, "daftra_fake", True)
    monkeypatch.setattr(settings, "daftra_subdomain", "fake")
    monkeypatch.setattr(settings, "daftra_api_key", "fake-key")
    monkeypatch.setattr(daftra.cache, "_cache", {})
    daftra.fake.use(fake)
    # Work order custom fields are read back after a pause; no need to wait in a test
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    yield fake
    daftra.fake.use(None)


@pytest.fixture(autouse=True)
def outbox(monkeypatch):
    sent = []
    monkeypatch.setattr(settings, "smtp_host", "smtp.test")
    monkeypatch.setattr(settings, "mail_from", "Portal <portal@test>")
    catch = lambda to, subject, text, html: sent.append({"to": to, "subject": subject, "text": text})  # noqa: E731
    # The senders inside the module call `service.send`; callers outside reach the same function
    # through the package, which bound it at import, so both names are caught.
    monkeypatch.setattr(mail.service, "send", catch)
    monkeypatch.setattr(mail, "send", catch)
    return sent


@pytest.fixture(autouse=True)
def plain_login(monkeypatch):
    # Most tests log admins in without the emailed code; the MFA tests turn it back on
    monkeypatch.setattr(settings, "require_admin_mfa", False)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


def make_user(db, username, *, admin=False, permissions=(), email=None, daftra_staff_id=None,
              full_name=None, password=PASSWORD):
    """A user holding exactly these permissions, through one role of their own."""
    user = User(username=username, email=email or f"{username}@test.local", full_name=full_name or username.title(),
                password_hash=hash_password(password) if password else None, is_admin=admin,
                daftra_staff_id=daftra_staff_id)
    if permissions:
        user.roles = [Role(name=f"role-{username}", permissions=list(permissions), pages=[])]
    db.add(user)
    db.commit()
    return user


def may_fill(*form_keys) -> list[str]:
    return [f"form.{key}.submit" for key in form_keys]


def may_review(*form_keys) -> list[str]:
    return [f"form.{key}.review" for key in form_keys]


# The forms a request can be made from, which is what the old «النماذج» page opened
VISIBLE_FORMS = ("new_sale", "contract_renewal", "maintenance", "balance_payment", "quotation",
                 "tech_extra_works")


def auth(user) -> dict:
    return {"Authorization": f"Bearer {create_token(user)}"}


@pytest.fixture
def sales(db):
    """A salesperson: may fill in every visible form, and nothing else."""
    return make_user(db, "sales1", permissions=may_fill(*VISIBLE_FORMS), daftra_staff_id=71,
                     full_name="Sales One")


@pytest.fixture
def manager(db):
    """A manager: may review every form, and fill in the visible ones — what managing «sales» meant."""
    return make_user(db, "manager1", permissions=may_review(*registry_keys()) + may_fill(*VISIBLE_FORMS),
                     daftra_staff_id=40, full_name="Manager One")


def registry_keys():
    from app.modules.form_engine import keys

    return keys()


@pytest.fixture
def admin(db):
    return make_user(db, "admin1", admin=True, full_name="Admin One")
