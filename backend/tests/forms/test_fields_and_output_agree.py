"""A form's two files agree: everything its output.py sends to Daftra is something its fields.py asks.

Hiding a field in fields.py while output.py still reads it would not fail when the form is saved —
it would fail at اعتماد, in front of a manager, or quietly send an empty value to Daftra. So each
output.py is read here, and every request field it reads must be one its form shows.

Also pinned here: the client document carries every field the clients module reads, so nothing
reaches Daftra's client by a name the form's output never mentions.
"""

import ast
import importlib
from pathlib import Path

import pytest

from app.modules.form_engine import DAFTRA_LIST_TYPES, all_forms
from app.modules.invoicing import ClientRecord

FORMS = Path(__file__).resolve().parents[2] / "app" / "forms"
CLIENTS = Path(__file__).resolve().parents[2] / "app" / "modules" / "clients" / "in_daftra.py"


def read_fields(path: Path) -> set[str]:
    """Every name read as d["x"], d.get("x"), data["x"] or data.get("x") in a file."""
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        target, key = None, None
        if isinstance(node, ast.Subscript):
            target, key = node.value, node.slice
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get"
              and node.args):
            target, key = node.func.value, node.args[0]
        if (isinstance(target, ast.Name) and target.id in ("d", "data")
                and isinstance(key, ast.Constant) and isinstance(key.value, str)):
            found.add(key.value)
    return found


def shown(spec) -> set[str]:
    """The fields the form asks — its own and its actions' — and the «…_name» validation keeps
    beside each list field."""
    names = set()
    for field in [*spec.fields(), *(field for action in spec.actions for field in action.fields)]:
        names.add(field["name"])
        if field["type"] in DAFTRA_LIST_TYPES or field.get("type") == "select":
            names.add(field["name"] + "_name")
    return names


WITH_OUTPUT = [spec for spec in all_forms() if (FORMS / spec.key / "output.py").exists()]


@pytest.mark.parametrize("spec", WITH_OUTPUT, ids=lambda spec: spec.key)
def test_output_reads_only_what_the_form_asks(spec):
    # LEGACY_FIELDS: read for a request an earlier version of the form wrote, and said so there
    legacy = getattr(importlib.import_module(f"app.forms.{spec.key}.output"), "LEGACY_FIELDS", set())
    unasked = read_fields(FORMS / spec.key / "output.py") - shown(spec) - legacy
    assert not unasked, f"{spec.key}/output.py reads fields its fields.py does not show: {sorted(unasked)}"


@pytest.mark.parametrize("spec", WITH_OUTPUT, ids=lambda spec: spec.key)
def test_a_form_with_output_approves_through_it(spec):
    output = importlib.import_module(f"app.forms.{spec.key}.output")
    assert spec.on_approve is output.on_approve
    assert getattr(output.on_approve, "documents", None) == tuple(output.DOCUMENTS)


def test_the_client_document_carries_everything_the_clients_module_reads():
    carried = set(ClientRecord().as_data())
    assert read_fields(CLIENTS) <= carried, sorted(read_fields(CLIENTS) - carried)


def test_the_check_would_catch_a_hidden_field(tmp_path):
    """The check itself: a read of a field the form does not show is found."""
    path = tmp_path / "output.py"
    path.write_text('def receipt(ctx):\n    d = ctx.data\n    return d.get("paid_amount"), d["treasury"]\n')
    assert read_fields(path) == {"paid_amount", "treasury"}
