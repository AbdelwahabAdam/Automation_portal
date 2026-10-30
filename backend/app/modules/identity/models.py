"""The tables identity owns: the users, the roles, and which user has which."""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Table, func, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ...core.database import Base
from ...core import permissions


user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class Role(Base):
    """A named set of permissions. A user holds the permissions of all their roles."""

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    permissions: Mapped[list[str]] = mapped_column(ARRAY(String(80)), default=list,
                                                   server_default=text("'{}'"))
    # What this role was before access became per form. Still written and read by the release
    # before this one, so it is dropped only by the release after it (final_plan.md §11).
    pages: Mapped[list[str]] = mapped_column(ARRAY(String(60)), default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    users: Mapped[list["User"]] = relationship(secondary=user_roles, back_populates="roles")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    # Lower case. Missing only on users created before email was required
    email: Mapped[str | None] = mapped_column(String(254), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120), default="")
    # Null until an invited user sets a password
    password_hash: Mapped[str | None] = mapped_column(String(100))
    # An admin opens every page, including the admin pages
    is_admin: Mapped[bool] = mapped_column(default=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(default=True)
    # What a user managing a department used to mean. Access is per form now, and the migration
    # gave today's managers a role instead; dropped by the release after this one.
    manages: Mapped[list[str]] = mapped_column(ARRAY(String(30)), default=list, server_default=text("'{}'"))
    # Two-step login chosen by the user; admins have it whatever this says (see mfa.applies)
    mfa_enabled: Mapped[bool] = mapped_column(default=False, server_default="false")
    # The emailed code waiting to be typed in: its hash, when it expires, when it was sent, wrong tries so far
    mfa_code_hash: Mapped[str | None] = mapped_column(String(64))
    mfa_code_expires: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mfa_code_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mfa_code_attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    # This user's staff id in Daftra; the sales person on the invoices their approved requests create
    daftra_staff_id: Mapped[int | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    roles: Mapped[list[Role]] = relationship(secondary=user_roles, back_populates="users", order_by=Role.name)

    @property
    def two_step(self) -> bool:
        from . import mfa  # mfa imports this module

        return mfa.applies(self)

    @property
    def has_password(self) -> bool:
        return bool(self.password_hash)

    @property
    def permissions(self) -> list[str]:
        """The keys this user holds: every one for an admin, else their roles' put together.

        Only declared and assignable keys count, so a key left in a role after the form or page
        it belonged to was removed grants nothing.
        """
        if self.is_admin:
            return permissions.assignable_keys() + sorted(permissions.ADMIN_ONLY)
        held = {key for role in self.roles for key in role.permissions}
        return [key for key in permissions.assignable_keys() if key in held]
