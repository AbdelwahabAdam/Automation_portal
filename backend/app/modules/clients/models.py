"""The tables clients owns: the customers, their addresses and their categories."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ...core.database import Base


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
    # False: the portal saved it but Daftra refused it. The nightly sync keeps such an address
    # instead of wiping it, and offers it to Daftra again before it reads the clients back.
    in_daftra: Mapped[bool] = mapped_column(default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    client: Mapped[Client] = relationship(back_populates="addresses")
