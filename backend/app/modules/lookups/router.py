"""Daftra's lists, for the forms' drop-downs, and the order sources page. Transport only."""

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...core.context import Actor
from ...core.database import get_db
from ...core.security import acting, form_user, require
from . import order_sources as sources
from . import service

router = APIRouter(prefix="/api")
may_keep = require("admin.order_sources")
admin_router = APIRouter(prefix="/api/admin", dependencies=[Depends(may_keep)])


class OrderSourceIn(BaseModel):
    name: str = Field(max_length=100)


class OrderSourceState(BaseModel):
    active: bool


@router.get("/daftra/staff")
def daftra_staff(user=Depends(form_user)):
    return service.staff()


@router.get("/daftra/staff_members")
def daftra_staff_members(user=Depends(form_user)):
    return service.staff_members()


@router.get("/daftra/treasuries")
def daftra_treasuries(user=Depends(form_user)):
    return service.treasuries()


@router.get("/daftra/order_sources")
def daftra_order_sources(user=Depends(form_user)):
    return service.order_sources()


# ---------- The «مصادر الطلب» admin page ----------


@admin_router.get("/order-sources")
def list_sources():
    return sources.all_sources()


@admin_router.post("/order-sources", status_code=status.HTTP_201_CREATED)
def add_source(body: OrderSourceIn, who: Actor = Depends(acting(may_keep)),
               db: Session = Depends(get_db)):
    return sources.add(db, who, body.name)


@admin_router.put("/order-sources/{source_id}")
def set_active(source_id: int, body: OrderSourceState, who: Actor = Depends(acting(may_keep)),
               db: Session = Depends(get_db)):
    return sources.set_active(db, who, source_id, body.active)
