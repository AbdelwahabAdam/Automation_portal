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

from app import daftra, mail  # noqa: E402
from app.config import settings  # noqa: E402
from app.database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Role, User  # noqa: E402
from app.security import create_token, hash_password  # noqa: E402

from .fake_daftra import FakeDaftra  # noqa: E402

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
    fake = FakeDaftra()
    monkeypatch.setattr(settings, "daftra_subdomain", "fake")
    monkeypatch.setattr(settings, "daftra_api_key", "fake-key")
    monkeypatch.setattr(daftra, "_call", fake)
    monkeypatch.setattr(daftra, "invoice_pdf", lambda invoice_id, url: b"%PDF-1.4 fake invoice")
    monkeypatch.setattr(daftra, "upload_file", fake.upload_file)
    monkeypatch.setattr(daftra, "_cache", {})
    # Work order custom fields are read back after a pause; no need to wait in a test
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    return fake


@pytest.fixture(autouse=True)
def outbox(monkeypatch):
    sent = []
    monkeypatch.setattr(settings, "smtp_host", "smtp.test")
    monkeypatch.setattr(settings, "mail_from", "Portal <portal@test>")
    monkeypatch.setattr(mail, "send", lambda to, subject, text, html: sent.append({"to": to, "subject": subject, "text": text}))
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


def make_user(db, username, *, admin=False, pages=(), manages=(), email=None, daftra_staff_id=None,
              full_name=None, password=PASSWORD):
    user = User(username=username, email=email or f"{username}@test.local", full_name=full_name or username.title(),
                password_hash=hash_password(password) if password else None, is_admin=admin,
                manages=list(manages), daftra_staff_id=daftra_staff_id)
    if pages:
        user.roles = [Role(name=f"role-{username}", pages=list(pages))]
    db.add(user)
    db.commit()
    return user


def auth(user) -> dict:
    return {"Authorization": f"Bearer {create_token(user)}"}


@pytest.fixture
def sales(db):
    return make_user(db, "sales1", pages=["sales.new_request", "sales.my_requests"], daftra_staff_id=71,
                     full_name="Sales One")


@pytest.fixture
def manager(db):
    return make_user(db, "manager1", manages=["sales"], daftra_staff_id=40, full_name="Manager One")


@pytest.fixture
def admin(db):
    return make_user(db, "admin1", admin=True, full_name="Admin One")
