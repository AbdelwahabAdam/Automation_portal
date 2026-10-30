"""A user or a role as the activity log records it, before and after a change."""

from .models import Role, User


def user_snapshot(user: User) -> dict:
    return {
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "is_admin": user.is_admin,
        "is_active": user.is_active,
        "roles": sorted(role.name for role in user.roles),
        "daftra_staff_id": user.daftra_staff_id,
    }


def role_snapshot(role: Role) -> dict:
    return {"name": role.name, "permissions": sorted(role.permissions)}
