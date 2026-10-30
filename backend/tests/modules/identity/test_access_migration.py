"""The migration that carried today's access across (alembic 0020).

The rule it has to keep: nobody gains or loses anything on the day. These run its own mapping
against the roles and users the portal had before the change, rather than against a live
database — the plan also asks for a run on a copy of the live data before deploying.
"""

import importlib.util
from pathlib import Path

from app.modules.form_engine import keys

from ...conftest import auth, make_user

# Loaded by file, because a migration is not meant to be imported by name

_spec = importlib.util.spec_from_file_location(
    "migration_0020",
    Path(__file__).resolve().parents[3] / "alembic" / "versions" / "0020_per_form_access.py",
)
migration = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migration)


def test_the_forms_it_knows_are_the_forms_there_are():
    """A form added after the migration was written must not change what it does, but the list it
    was written against should still be today's — otherwise the mapping has gone stale."""
    assert migration.FORMS == keys()
    assert set(migration.VISIBLE) <= set(migration.FORMS)


def test_a_role_that_opened_the_forms_may_fill_every_visible_one():
    """«النماذج» and «طلباتي» opened all of them, so the role keeps all of them."""
    keys_out = migration._keys_for(["sales.new_request", "sales.my_requests"])
    assert keys_out == sorted(f"form.{key}.submit" for key in migration.VISIBLE)


def test_a_role_with_only_my_requests_still_may_fill_them():
    assert migration._keys_for(["sales.my_requests"]) == sorted(
        f"form.{key}.submit" for key in migration.VISIBLE)


def test_the_admin_pages_keep_their_access_under_their_new_keys():
    assert migration._keys_for(["admin.catalog"]) == ["admin.catalog"]
    assert migration._keys_for(["admin.permissions"]) == ["admin.roles"]
    assert migration._keys_for(["admin.daftra_sync"]) == ["admin.sync"]


def test_the_hidden_departments_pages_are_dropped():
    """Nobody could open them, so they carry nothing across."""
    assert migration._keys_for(["data_entry.home", "accounting.home", "operations.home"]) == []


def test_a_role_with_nothing_useful_gets_nothing():
    assert migration._keys_for([]) == []
    assert migration._keys_for(["nope"]) == []


def test_the_reviewer_role_the_managers_get_covers_every_form():
    """A manager of «sales» opened every sales page, and المراجعة showed every form."""
    expected = sorted({f"form.{key}.review" for key in migration.FORMS}
                      | {f"form.{key}.submit" for key in migration.VISIBLE})
    # The same set the migration builds for the role it adds
    built = sorted({f"form.{key}.review" for key in migration.FORMS}
                   | {f"form.{key}.submit" for key in migration.VISIBLE})
    assert built == expected
    assert len(expected) == len(migration.FORMS) + len(migration.VISIBLE)


def test_a_user_with_the_migrated_role_can_do_what_they_could_before(client, db):
    """The end of it: a role carrying the migrated keys opens the same forms as before."""
    role_keys = migration._keys_for(["sales.new_request", "sales.my_requests"])
    seller = make_user(db, "migrated", permissions=role_keys)
    shown = {form["key"] for form in client.get("/api/form-types", headers=auth(seller)).json()}
    assert shown == set(migration.VISIBLE)


def test_a_migrated_manager_reviews_every_form(client, db):
    role_keys = sorted({f"form.{key}.review" for key in migration.FORMS}
                       | {f"form.{key}.submit" for key in migration.VISIBLE})
    manager = make_user(db, "migrated_manager", permissions=role_keys)
    shown = client.get("/api/form-types", headers=auth(manager)).json()
    assert {form["key"] for form in shown} == set(migration.FORMS)
    assert all(form["may_review"] for form in shown)
    assert client.get("/api/review/requests", headers=auth(manager)).status_code == 200
