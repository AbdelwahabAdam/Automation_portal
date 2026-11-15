"""The queries on clients' own tables. No commits, no decisions."""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .models import Address, Client, ClientCategory

# Shorter than this is not a phone number worth searching for
MIN_PHONE_DIGITS = 9


def _with_addresses():
    return select(Client).options(selectinload(Client.addresses))


def by_code(db: Session, code: str) -> Client | None:
    return db.scalar(_with_addresses().where(Client.client_code == code))


def by_phone(db: Session, phone: str) -> list[Client]:
    """The clients whose own number this is. Not their رقم مسؤول اخر (phone2): that is often someone
    else's — a relative, a mosque's caretaker — who may be a client in their own right. Matched on
    it, a new client's request was put on the client whose contact they were (request 162,
    2026-11-15: حمد السناني's number was محمد سعيد سهيل's second one)."""
    return list(db.scalars(_with_addresses().where(Client.phone == phone)))


def by_daftra_id(db: Session, daftra_id: int) -> Client | None:
    return db.scalar(select(Client).where(Client.daftra_id == daftra_id))


def code_exists(db: Session, code: str) -> bool:
    return db.scalar(select(Client.id).where(Client.client_code == code).limit(1)) is not None


def phone_exists(db: Session, phone: str) -> bool:
    """Whether this is some client's own number (not a رقم مسؤول اخر: see by_phone)."""
    return db.scalar(select(Client.id).where(Client.phone == phone).limit(1)) is not None


def add_address(db: Session, client: Client, fields: dict) -> Address:
    address = Address(client_id=client.id, **fields)
    db.add(address)
    return address


def categories(db: Session) -> list[ClientCategory]:
    return list(db.scalars(select(ClientCategory).order_by(ClientCategory.name)))
