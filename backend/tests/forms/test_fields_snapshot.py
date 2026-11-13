"""Every form is exactly what it was: its sections and fields, as the browser receives them.

The guard for the forms refactor (`forms_plan.md`): moving a form from `definition.py` to
`fields.py` is a change of shape, never of behaviour. Each form's `GET /api/form-types` entry is
saved under tests/forms/snapshots/<key>.json, and a refactored form passes only if it produces the
very same JSON, key for key.

A deliberate change to a form — a field made optional, a new label — is a real change, so its
snapshot is rewritten on purpose and the difference shows in review:

    ./run-tests.sh tests/forms/test_fields_snapshot.py --update-snapshots
"""

import json
from pathlib import Path

import pytest

from app.modules.form_engine import all_forms

SNAPSHOTS = Path(__file__).parent / "snapshots"


def as_sent(spec) -> str:
    """The form as the browser gets it, written so that a change reads as one line in a diff."""
    return json.dumps(spec.as_api(), ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def snapshot_of(key: str) -> Path:
    return SNAPSHOTS / f"{key}.json"


@pytest.fixture(scope="module")
def update(request) -> bool:
    return request.config.getoption("--update-snapshots")


@pytest.mark.parametrize("spec", all_forms(), ids=lambda spec: spec.key)
def test_the_form_is_sent_exactly_as_it_was(spec, update):
    path = snapshot_of(spec.key)
    sent = as_sent(spec)
    if update:
        SNAPSHOTS.mkdir(exist_ok=True)
        path.write_text(sent, encoding="utf-8")
        return
    assert path.exists(), f"no snapshot for {spec.key}: run with --update-snapshots once, on purpose"
    saved = path.read_text(encoding="utf-8")
    # Compared as data first, so the failure names what changed rather than dumping two files
    assert json.loads(sent) == json.loads(saved), f"{spec.key} is no longer sent as it was"
    assert sent == saved


def test_every_snapshot_belongs_to_a_form(update):
    """A form removed or renamed leaves its snapshot behind, which is a form that went missing."""
    if update:
        return
    saved = {path.stem for path in SNAPSHOTS.glob("*.json")}
    assert saved == {spec.key for spec in all_forms()}
