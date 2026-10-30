"""The users and roles screens. Transport only."""

from datetime import datetime

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from ....core.context import Actor
from ....core.database import get_db
from ....core.errors import ExternalFailure
from ....core.security import acting, require_admin
from ....integrations import daftra
from ....core import permissions
from ..models import Role, User
from ..service import roles as roles_service
from ..service import users as users_service

router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])


class RoleIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    permissions: list[str]


class RoleOut(BaseModel):
    id: int
    name: str
    permissions: list[str]
    user_count: int


class RoleRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str | None
    full_name: str
    is_admin: bool
    is_active: bool
    # False until an invited user has set a password
    has_password: bool
    # Logs in with an emailed code after the password: every admin, and users who turned it on
    two_step: bool
    daftra_staff_id: int | None
    created_at: datetime
    roles: list[RoleRef]


class InviteOut(BaseModel):
    user: AdminUserOut
    email_sent: bool
    # Given to the admin to pass on by hand, only when the email could not be sent
    link: str | None


class UserCreate(BaseModel):
    username: str
    email: str
    full_name: str = Field(min_length=1, max_length=120)
    role_ids: list[int] = []
    is_admin: bool = False
    daftra_staff_id: int | None = None


class UserUpdate(BaseModel):
    email: str
    full_name: str = Field(min_length=1, max_length=120)
    role_ids: list[int]
    is_admin: bool
    is_active: bool
    daftra_staff_id: int | None = None


def invited(result) -> InviteOut:
    user, sent, link = result
    return InviteOut(user=AdminUserOut.model_validate(user), email_sent=sent, link=link)


def existing_role(role_id: int, db: Session = Depends(get_db)) -> Role:
    return roles_service.by_id(db, role_id)


def existing_user(user_id: int, db: Session = Depends(get_db)) -> User:
    return users_service.by_id(db, user_id)


# ---------- Roles ----------


@router.get("/permissions")
def assignable_permissions():
    """Everything a role can be given, for the two tabs of الأدوار والصلاحيات.

    `forms` is one row per form with its three keys (تعبئة · عرض · مراجعة); `admin_pages` is the
    admin pages a role may hold. The two that only an admin may hold are not offered.
    """
    forms, seen = [], {}
    for permission in permissions.all_permissions():
        if permission.kind != "form" or not permission.assignable:
            continue
        row = seen.get(permission.form)
        if row is None:
            # The label of a form's permission is "<what> — <the form's name>"
            row = {"key": permission.form, "label": permission.label.split("—", 1)[-1].strip(), "keys": {}}
            seen[permission.form] = row
            forms.append(row)
        row["keys"][permission.does] = permission.key
    return {
        "forms": forms,
        "what": permissions.WHAT,
        "admin_pages": [{"key": p.key, "label": p.label} for p in permissions.all_permissions()
                        if p.kind == "admin" and p.assignable],
    }


@router.get("/roles", response_model=list[RoleOut])
def list_roles(db: Session = Depends(get_db)):
    return roles_service.listed(db)


@router.post("/roles", response_model=RoleOut, status_code=status.HTTP_201_CREATED)
def create_role(body: RoleIn, who: Actor = Depends(acting(require_admin)), db: Session = Depends(get_db)):
    return roles_service.create(db, who, body.name, body.permissions)


@router.put("/roles/{role_id}", response_model=RoleOut)
def update_role(body: RoleIn, role: Role = Depends(existing_role),
                who: Actor = Depends(acting(require_admin)), db: Session = Depends(get_db)):
    return roles_service.update(db, who, role, body.name, body.permissions)


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(role: Role = Depends(existing_role), who: Actor = Depends(acting(require_admin)),
                db: Session = Depends(get_db)):
    roles_service.delete(db, who, role)


# ---------- Users ----------


@router.get("/users", response_model=list[AdminUserOut])
def list_users(db: Session = Depends(get_db)):
    return users_service.listed(db)


@router.get("/daftra/staff")
def daftra_staff_members():
    """Daftra's active staff with ids, to link a portal user to the staff member on their invoices."""
    try:
        return daftra.list_staff_members()
    except daftra.DaftraError:
        raise ExternalFailure("تعذر تحميل الموظفين من دفترة")


@router.post("/users", response_model=InviteOut, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, who: Actor = Depends(acting(require_admin)), db: Session = Depends(get_db)):
    return invited(users_service.create(db, who, body))


@router.put("/users/{user_id}", response_model=AdminUserOut)
def update_user(body: UserUpdate, user: User = Depends(existing_user),
                who: Actor = Depends(acting(require_admin)), db: Session = Depends(get_db)):
    return users_service.update(db, who, user, body)


@router.post("/users/{user_id}/invite", response_model=InviteOut)
def invite_user(user: User = Depends(existing_user), who: Actor = Depends(acting(require_admin)),
                db: Session = Depends(get_db)):
    return invited(users_service.invite_again(db, who, user))


@router.post("/users/{user_id}/mfa-reset", response_model=AdminUserOut)
def reset_mfa(user: User = Depends(existing_user), who: Actor = Depends(acting(require_admin)),
              db: Session = Depends(get_db)):
    return users_service.reset_two_step(db, who, user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user: User = Depends(existing_user), who: Actor = Depends(acting(require_admin)),
                db: Session = Depends(get_db)):
    users_service.delete(db, who, user)
