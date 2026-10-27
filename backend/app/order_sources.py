"""The «مصادر الطلب» admin page: Daftra's order sources (an invoice's مصدر الطلب), adding one, and
turning one on or off.

They live in Daftra only; the sales forms read the active ones from there (daftra.list_order_sources).
Renaming or deleting one is done in Daftra itself (its API cannot delete one).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from . import daftra
from .audit import Audit
from .database import get_db
from .models import User
from .security import require_admin
from .text import squash

router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])


class OrderSourceIn(BaseModel):
    name: str = Field(max_length=100)


class OrderSourceState(BaseModel):
    active: bool


def _all() -> list[dict]:
    try:
        return daftra.all_order_sources()
    except daftra.DaftraError:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "تعذر تحميل مصادر الطلب من دفترة")


@router.get("/order-sources")
def list_sources():
    return _all()


@router.post("/order-sources", status_code=status.HTTP_201_CREATED)
def add_source(body: OrderSourceIn, admin: User = Depends(require_admin), audit: Audit = Depends(),
               db: Session = Depends(get_db)):
    name = squash(body.name)
    if len(name) < 2:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "اكتب اسم مصدر الطلب")
    same = next((row for row in _all() if daftra.same_name(row["name"]) == daftra.same_name(name)), None)
    if same is not None:
        state = "" if same["active"] else "، وهو غير مفعّل — فعّله من دفترة بدل إضافة مصدر جديد"
        raise HTTPException(status.HTTP_409_CONFLICT, f"يوجد مصدر بنفس الاسم في دفترة: «{same['name']}»{state}")
    try:
        source_id = daftra.create_order_source(name)
    except daftra.DaftraError as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"تعذر إضافة المصدر في دفترة: {error}")
    audit.log(admin, "order_source.create", "order_source", source_id, name, after={"name": name})
    db.commit()
    return next((row for row in _all() if row["id"] == source_id),
                {"id": source_id, "name": name, "active": True, "display_order": 0})


@router.put("/order-sources/{source_id}")
def set_active(source_id: int, body: OrderSourceState, admin: User = Depends(require_admin), audit: Audit = Depends(),
               db: Session = Depends(get_db)):
    current = next((row for row in _all() if row["id"] == source_id), None)
    if current is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "مصدر الطلب غير موجود في دفترة")
    if current["active"] == body.active:
        return current
    try:
        saved = daftra.set_order_source_active(source_id, body.active)
    except daftra.DaftraError as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"تعذر تغيير حالة المصدر في دفترة: {error}")
    audit.log(admin, "order_source.update", "order_source", source_id, saved["name"],
              before={"active": current["active"]}, after={"active": body.active})
    db.commit()
    return saved
