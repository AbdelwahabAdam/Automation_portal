"""The roles screen: a named list of pages, and who holds it."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ....core.context import Actor
from ....core.errors import Conflict, Invalid, NotFound
from ....core.permissions import assignable_keys
from ...audit import changes
from ...audit import log as audit_log
from ..models import Role
from ..snapshots import role_snapshot


def role_out(role: Role) -> dict:
    return {"id": role.id, "name": role.name, "permissions": role.permissions,
            "user_count": len(role.users)}


def listed(db: Session) -> list[dict]:
    roles = db.scalars(select(Role).options(selectinload(Role.users)).order_by(Role.name))
    return [role_out(role) for role in roles]


def by_id(db: Session, role_id: int) -> Role:
    role = db.get(Role, role_id)
    if role is None:
        raise NotFound("الدور غير موجود")
    return role


def _clean(db: Session, name: str, keys: list[str], current: Role | None = None) -> tuple[str, list[str]]:
    name = name.strip()
    if not name:
        raise Invalid("اكتب اسم الدور")
    taken = db.scalar(select(Role).where(func.lower(Role.name) == name.lower()))
    if taken is not None and taken is not current:
        raise Conflict("يوجد دور بنفس الاسم")
    # Kept in declaration order; unknown and admin-only keys are dropped, so a role can never
    # carry a permission for a form that no longer exists, nor one only an admin may hold
    return name, [key for key in assignable_keys() if key in set(keys)]


def create(db: Session, who: Actor, name: str, keys: list[str]) -> dict:
    name, keys = _clean(db, name, keys)
    role = Role(name=name, permissions=keys, pages=[])
    db.add(role)
    db.flush()
    audit_log(db, who, "role.create", "role", role.id, role.name, after=role_snapshot(role))
    db.commit()
    return role_out(role)


def update(db: Session, who: Actor, role: Role, name: str, keys: list[str]) -> dict:
    before = role_snapshot(role)
    role.name, role.permissions = _clean(db, name, keys, role)
    old, new = changes(before, role_snapshot(role))
    if new:
        audit_log(db, who, "role.update", "role", role.id, role.name, old, new)
    db.commit()
    return role_out(role)


def delete(db: Session, who: Actor, role: Role):
    if role.users:
        raise Conflict("الدور مُسند لمستخدمين؛ أزله عنهم أولًا")
    audit_log(db, who, "role.delete", "role", role.id, role.name, before=role_snapshot(role))
    db.delete(role)
    db.commit()
