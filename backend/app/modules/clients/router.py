"""The customers, as the forms ask for them. Transport only, with the same paths as before."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...core.context import Actor
from ...core.database import get_db
from ...core.errors import ExternalFailure, Invalid
from ...core.security import acting, form_user
from ...integrations.daftra import DaftraError
from . import location, service

router = APIRouter(prefix="/api")


class AddressIn(BaseModel):
    emirate: str = Field("", max_length=50)
    area: str = Field("", max_length=100)
    street: str = Field("", max_length=200)
    house: str = Field("", max_length=100)
    location_url: str = Field("", max_length=600)
    coordinates: str = Field("", max_length=100)


@router.get("/location/from-link")
def point_of_link(url: str, user=Depends(form_user)):
    """Where a map link points, so pasting one moves the pin. The browser cannot follow a short
    link itself — reading another site's redirect is not allowed — so it is followed here."""
    try:
        lat, lng = location.resolve(url)
    except location.NotALocation as why:
        raise Invalid(str(why)) from why
    return {"lat": lat, "lng": lng}


@router.get("/clients/lookup")
def lookup_client(phone: str = "", code: str = "", user=Depends(form_user), db: Session = Depends(get_db)):
    """Finds a client in our own copy of Daftra's client list, by phone number or client code.

    The address filled in is the last one on file for that client; "addresses" lists all of
    them, so the sales form can offer a different one or let the user add a new one.
    """
    return {"matches": [service.client_match(c) for c in service.lookup(db, phone, code)]}


@router.post("/clients/{daftra_id}/addresses")
def add_client_address(daftra_id: int, body: AddressIn, who: Actor = Depends(acting(form_user)),
                       db: Session = Depends(get_db)):
    """Adds a new address for a client already in our list, e.g. when they have moved."""
    address, saved_in_daftra, problem = service.add_address(db, who, daftra_id, body.model_dump())
    return {**address, "saved_in_daftra": saved_in_daftra, "daftra_error": problem}


@router.get("/daftra/client_categories")
def daftra_client_categories(user=Depends(form_user), db: Session = Depends(get_db)):
    """Our copy of Daftra's client categories, each with the الإمارة and المنطقة it fills in."""
    return service.categories(db)


@router.get("/daftra/clients/{daftra_id}")
def daftra_client(daftra_id: int, user=Depends(form_user)):
    """What a form needs to know about a client from Daftra itself: their current category, and
    the invoices that still have something to pay (newest first, labelled for the drop-down)."""
    try:
        return service.details_from_daftra(daftra_id)
    except DaftraError:
        raise ExternalFailure("تعذر تحميل بيانات العميل من دفترة")
