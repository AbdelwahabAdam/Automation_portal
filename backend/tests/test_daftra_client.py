"""The Daftra client itself (app.daftra._call), with urlopen replaced: retries, errors, lookups."""

import io
import json
import urllib.error
import urllib.request

import pytest

from app import daftra
from app.daftra import _call as real_call  # taken before the fake_daftra fixture replaces it


class Answers:
    """Stands in for urlopen: gives each prepared answer in turn and records the requests."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.requests = []

    def __call__(self, request, timeout=None):
        self.requests.append(request)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return io.BytesIO(json.dumps(answer).encode())


def http_error(code, body=b'{"message": "no"}'):
    return urllib.error.HTTPError("https://fake", code, "error", {}, io.BytesIO(body))


@pytest.fixture
def answers(monkeypatch):
    def use(*items):
        fake = Answers(*items)
        monkeypatch.setattr(urllib.request, "urlopen", fake)
        return fake
    return use


def test_a_read_is_tried_again_once(answers):
    fake = answers(urllib.error.URLError("reset"), {"ok": 1})
    assert real_call("GET", "/api2/clients.json", {"limit": 1}) == {"ok": 1}
    assert len(fake.requests) == 2
    fake = answers(http_error(503), {"ok": 2})
    assert real_call("GET", "/api2/clients.json") == {"ok": 2}


def test_a_read_failing_twice_is_an_error(answers):
    answers(TimeoutError(), TimeoutError())
    with pytest.raises(daftra.DaftraError):
        real_call("GET", "/api2/clients.json")


def test_a_write_is_never_tried_twice(answers):
    fake = answers(urllib.error.URLError("reset"), {"id": 1})
    with pytest.raises(daftra.DaftraError):
        real_call("POST", "/api2/invoices.json", None, {"Invoice": {}})
    assert len(fake.requests) == 1


def test_daftras_own_message_is_kept_and_404_is_not_found(answers):
    answers(http_error(422, b'{"message": "Invalid", "validation_errors": {"client_email": "required"}}'))
    with pytest.raises(daftra.DaftraError) as refused:
        real_call("POST", "/api2/clients.json", None, {})
    assert "client_email" in str(refused.value) and "HTTP 422" in str(refused.value)
    answers(http_error(404))
    with pytest.raises(daftra.NotFound):
        real_call("GET", "/api2/invoices/1.json")


def test_the_request_carries_the_key_and_json(answers):
    fake = answers({"id": 5})
    real_call("POST", "/api2/invoices.json", {"x": 1}, {"Invoice": {"note": "عربي"}})
    sent = fake.requests[0]
    assert sent.full_url == "https://fake.daftra.com/api2/invoices.json?x=1"
    assert sent.get_header("Apikey") == "fake-key"
    assert json.loads(sent.data) == {"Invoice": {"note": "عربي"}}


def test_local_phone_and_invoice_label():
    assert daftra.local_phone("+971 50 123 4567") == "0501234567"
    assert daftra.local_phone("00971501234567") == "0501234567"
    assert daftra.local_phone("501234567") == "0501234567"
    assert daftra.local_phone(None) == ""
    label = daftra.invoice_label({"no": "06273", "date": "18/10/2026", "unpaid": 4650.0})
    assert label == "06273 — 18/10/2026 — المتبقي 4,650 درهم"


def test_lists_are_cached_and_kept_when_daftra_is_down(fake_daftra):
    assert [t["id"] for t in daftra.list_treasuries()] == [13, 9]
    calls = len(fake_daftra.calls)
    daftra.list_treasuries()
    assert len(fake_daftra.calls) == calls
    # Expired, and Daftra failing: the list already loaded is kept
    daftra._cache["treasuries"] = (0, daftra._cache["treasuries"][1])
    fake_daftra.fail_once = "/api2/treasuries.json"
    assert [t["id"] for t in daftra.list_treasuries()] == [13, 9]
