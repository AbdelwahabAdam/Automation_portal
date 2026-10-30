"""The queries on clients' own tables. No commits, no decisions."""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from .models import Address, Client, ClientCategory

# Shorter than this is not a phone number worth searching for
MIN_PHONE_DIGITS = 9


def _with_addresses():
    return select(Client).options(selectinload(Client.addresses))


def by_code(db: Session, code: str) -> Client | None:
    return db.scalar(_with_addresses().where(Client.client_code == code))


def by_phone(db: Session, phone: str) -> list[Client]:
    return list(db.scalars(_with_addresses().where(or_(Client.phone == phone, Client.phone2 == phone))))


def by_daftra_id(db: Session, daftra_id: int) -> Client | None:
    return db.scalar(select(Client).where(Client.daftra_id == daftra_id))


def code_exists(db: Session, code: str) -> bool:
    return db.scalar(select(Client.id).where(Client.client_code == code).limit(1)) is not None


def phone_exists(db: Session, phone: str) -> bool:
    return db.scalar(
        select(Client.id).where(or_(Client.phone == phone, Client.phone2 == phone)).limit(1)
    ) is not None


def add_address(db: Session, client: Client, fields: dict) -> Address:
    address = Address(client_id=client.id, **fields)
    db.add(address)
    return address


def categories(db: Session) -> list[ClientCategory]:
    return list(db.scalars(select(ClientCategory).order_by(ClientCategory.name)))
