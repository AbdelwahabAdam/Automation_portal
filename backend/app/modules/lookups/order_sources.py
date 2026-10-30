"""The «مصادر الطلب» admin page: Daftra's order sources (an invoice's مصدر الطلب), adding one,
and turning one on or off.

They live in Daftra only; the forms read the active ones from there. Renaming or deleting one is
done in Daftra itself (its API cannot delete one).
"""

from sqlalchemy.orm import Session

from ...core.context import Actor
from ...core.errors import Conflict, ExternalFailure, Invalid, NotFound
from ...core.text import squash
from ...integrations import daftra
from ..audit import log as audit_log

# Shorter than this is not a name
MIN_NAME = 2


def all_sources() -> list[dict]:
    try:
        return daftra.all_order_sources()
    except daftra.DaftraError:
        raise ExternalFailure("تعذر تحميل مصادر الطلب من دفترة")


def add(db: Session, who: Actor, raw_name: str) -> dict:
    name = squash(raw_name)
    if len(name) < MIN_NAME:
        raise Invalid("اكتب اسم مصدر الطلب")
    same = next((row for row in all_sources() if daftra.same_name(row["name"]) == daftra.same_name(name)), None)
    if same is not None:
        state = "" if same["active"] else "، وهو غير مفعّل — فعّله من دفترة بدل إضافة مصدر جديد"
        raise Conflict(f"يوجد مصدر بنفس الاسم في دفترة: «{same['name']}»{state}")
    try:
        source_id = daftra.create_order_source(name)
    except daftra.DaftraError as error:
        raise ExternalFailure(f"تعذر إضافة المصدر في دفترة: {error}")
    audit_log(db, who, "order_source.create", "order_source", source_id, name, after={"name": name})
    db.commit()
    return next((row for row in all_sources() if row["id"] == source_id),
                {"id": source_id, "name": name, "active": True, "display_order": 0})


def set_active(db: Session, who: Actor, source_id: int, active: bool) -> dict:
    current = next((row for row in all_sources() if row["id"] == source_id), None)
    if current is None:
        raise NotFound("مصدر الطلب غير موجود في دفترة")
    if current["active"] == active:
        return current
    try:
        saved = daftra.set_order_source_active(source_id, active)
    except daftra.DaftraError as error:
        raise ExternalFailure(f"تعذر تغيير حالة المصدر في دفترة: {error}")
    audit_log(db, who, "order_source.update", "order_source", source_id, saved["name"],
              before={"active": current["active"]}, after={"active": active})
    db.commit()
    return saved
