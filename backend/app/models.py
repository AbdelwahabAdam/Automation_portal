from datetime import datetime
from decimal import Decimal

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, Table, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base
from .pages import ADMIN_DEPARTMENT, ALL_PAGE_KEYS, ASSIGNABLE_PAGE_KEYS, department_of

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class Role(Base):
    """A named list of pages. A user opens the pages of all their roles."""

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)
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
    # Keys of the departments this user manages; a manager opens every page of the department
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
    def pages(self) -> list[str]:
        if self.is_admin:
            return ALL_PAGE_KEYS
        from_roles = {key for role in self.roles for key in role.pages} & set(ASSIGNABLE_PAGE_KEYS)
        managed = set(self.manages) - {ADMIN_DEPARTMENT}
        return [key for key in ALL_PAGE_KEYS if key in from_roles or department_of(key) in managed]


class Request(Base):
    __tablename__ = "requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    form_type: Mapped[str] = mapped_column(String(50), index=True)
    data: Mapped[dict] = mapped_column(JSONB)
    # draft -> submitted -> returned (to the owner, with a reason) or approved; returned -> submitted again
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    # Goes up each time the request is submitted, so a decision applies to the version that was reviewed
    revision: Mapped[int] = mapped_column(default=0, server_default="0")
    returned_reason: Mapped[str | None] = mapped_column(Text)
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # What approving the request created in Daftra. Each id is kept as soon as its step succeeds,
    # so approving again after a failure carries on instead of creating it twice.
    daftra_client_id: Mapped[int | None]
    daftra_invoice_id: Mapped[int | None]
    daftra_invoice_no: Mapped[str | None] = mapped_column(String(30))
    daftra_payment_id: Mapped[int | None]
    daftra_receipt_no: Mapped[str | None] = mapped_column(String(30))
    daftra_work_order_id: Mapped[int | None]
    daftra_work_order_no: Mapped[str | None] = mapped_column(String(30))
    # Why the last attempt to create them failed; cleared once they all exist
    daftra_error: Mapped[str | None] = mapped_column(Text)
    daftra_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_by: Mapped[User] = relationship(foreign_keys=[created_by_id])
    reviewed_by: Mapped[User | None] = relationship(foreign_keys=[reviewed_by_id])
    events: Mapped[list["RequestEvent"]] = relationship(
        back_populates="request", cascade="all, delete-orphan", order_by="RequestEvent.id"
    )
    attachments: Mapped[list["Attachment"]] = relationship(
        back_populates="request", cascade="all, delete-orphan", order_by="Attachment.id"
    )


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id", ondelete="CASCADE"), index=True)
    field: Mapped[str] = mapped_column(String(50))
    filename: Mapped[str] = mapped_column(String(255))
    stored_name: Mapped[str] = mapped_column(String(80))
    content_type: Mapped[str] = mapped_column(String(100))
    size: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    request: Mapped[Request] = relationship(back_populates="attachments")


class AuditLog(Base):
    """One row per action. Rows are only ever added, never changed or deleted."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    # Null for a failed login; username keeps the name as it was at the time
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    username: Mapped[str] = mapped_column(String(50), default="")
    action: Mapped[str] = mapped_column(String(40), index=True)
    entity_type: Mapped[str] = mapped_column(String(30), default="")
    entity_id: Mapped[int | None]
    # Short readable name of the record, e.g. a username or a request's customer
    entity_label: Mapped[str] = mapped_column(String(160), default="")
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)
    ip: Mapped[str] = mapped_column(String(45), default="")
    user_agent: Mapped[str] = mapped_column(String(300), default="")


class Product(Base):
    """A single unit that is sold or installed, with nothing else inside it."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Its id in the final catalog workbook (e.g. "FL-I012"), so a re-import matches by it, not by name
    sku: Mapped[str | None] = mapped_column(String(20), unique=True)
    # Daftra's own product id, so a re-import from products.json matches the same row, not by name
    daftra_id: Mapped[int | None] = mapped_column(unique=True)
    # Its image in Daftra (ProductImageS3), as a file id: what the work order's صورة المنتج holds
    file_id: Mapped[int | None]
    # As written on quotations and invoices
    name: Mapped[str] = mapped_column(String(200), unique=True)
    name_ar: Mapped[str] = mapped_column(String(200), default="", server_default="")
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    # The usual price; a package line can charge a different one
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0, server_default="0")
    price_includes_tax: Mapped[bool] = mapped_column(default=True, server_default="true")
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.05"), server_default="0.05")
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")
    # Daftra reference fields, kept for traceability; filled by the Daftra import, editable by admins
    product_code: Mapped[str | None] = mapped_column(String(50))
    barcode: Mapped[str | None] = mapped_column(String(50))
    buy_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    stock_balance: Mapped[int | None]
    category: Mapped[str | None] = mapped_column(String(200))
    brand: Mapped[str | None] = mapped_column(String(100))
    # Offered as an item on طلب صيانة وتبديل under this group (e.g. «الفلاتر»); None: not offered there
    maintenance_group: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Package(Base):
    """One or more products sold together under one name, e.g. a cooler with its cover, filter and fitting."""

    __tablename__ = "packages"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Short reference such as FLP-001; optional
    code: Mapped[str | None] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    color: Mapped[str] = mapped_column(String(40), default="", server_default="")
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    items: Mapped[list["PackageItem"]] = relationship(
        back_populates="package", cascade="all, delete-orphan", order_by="PackageItem.sort_order"
    )


class PackageItem(Base):
    """A product inside a package, with the quantity and price it has in that package."""

    __tablename__ = "product_to_package"

    package_id: Mapped[int] = mapped_column(ForeignKey("packages.id", ondelete="CASCADE"), primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), primary_key=True, index=True)
    quantity: Mapped[int] = mapped_column(default=1, server_default="1")
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    price_includes_tax: Mapped[bool] = mapped_column(default=True, server_default="true")
    # Taken off this line's total, tax included
    discount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0, server_default="0")
    sort_order: Mapped[int] = mapped_column(default=0, server_default="0")

    package: Mapped[Package] = relationship(back_populates="items")
    product: Mapped[Product] = relationship()


class ClientCategory(Base):
    """A Daftra client category (التصنيف), copied once from Daftra (app.import_client_categories) so the
    forms read it from here. emirate/area: where its clients mostly live, to fill in the address."""

    __tablename__ = "client_categories"

    # Daftra's id for the category
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(200))
    emirate: Mapped[str | None] = mapped_column(String(50))
    area: Mapped[str | None] = mapped_column(String(100))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Client(Base):
    """A Daftra client, kept locally so a sales form can look one up without calling Daftra.

    Loaded from Daftra's client export (app.import_clients); only clients with a phone number
    are kept, since phone is how the sales forms look one up.
    """

    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True)
    daftra_id: Mapped[int] = mapped_column(unique=True)
    client_code: Mapped[str] = mapped_column(String(10), unique=True)
    customer_name: Mapped[str] = mapped_column(String(200), default="", server_default="")
    phone: Mapped[str] = mapped_column(String(20), index=True, default="", server_default="")
    phone2: Mapped[str] = mapped_column(String(20), default="", server_default="")
    email: Mapped[str] = mapped_column(String(200), default="", server_default="")
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    addresses: Mapped[list["Address"]] = relationship(
        back_populates="client", cascade="all, delete-orphan", order_by="Address.is_default.desc()"
    )


class Address(Base):
    """One of a client's addresses; a client can have more than one (Daftra keeps a list too)."""

    __tablename__ = "addresses"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    emirate: Mapped[str] = mapped_column(String(50), default="", server_default="")
    area: Mapped[str] = mapped_column(String(100), default="", server_default="")
    street: Mapped[str] = mapped_column(String(200), default="", server_default="")
    house: Mapped[str] = mapped_column(String(100), default="", server_default="")
    # Google Maps link for this address, e.g. https://maps.app.goo.gl/...
    link: Mapped[str] = mapped_column(String(600), default="", server_default="")
    is_default: Mapped[bool] = mapped_column(default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    client: Mapped[Client] = relationship(back_populates="addresses")


class RequestEvent(Base):
    """One step in a request's history: created, submitted, returned with a reason, approved."""

    __tablename__ = "request_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id", ondelete="CASCADE"), index=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    # Name at the time, kept if the user is later deleted
    username: Mapped[str] = mapped_column(String(120), default="")
    kind: Mapped[str] = mapped_column(String(30))
    revision: Mapped[int] = mapped_column(default=0)
    note: Mapped[str | None] = mapped_column(Text)

    request: Mapped[Request] = relationship(back_populates="events")


class SyncRun(Base):
    """One refresh of our copy of a Daftra list (products or clients), from the «المزامنة مع دفترة»
    admin page or the nightly client job, with what it changed (summary) or why it failed."""

    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    # "products" or "clients" (app.daftra_refresh.KINDS)
    kind: Mapped[str] = mapped_column(String(20), index=True)
    # queued -> running -> done | failed
    status: Mapped[str] = mapped_column(String(10))
    started_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    # Name at the time (or «المزامنة الليلية»), kept if the user is later deleted
    started_by_name: Mapped[str] = mapped_column(String(120), default="", server_default="")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    summary: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str] = mapped_column(Text, default="", server_default="")
