"""Bringing our copies of Daftra's lists up to date: the «المزامنة مع دفترة» admin page.

Products: only the catalog's products linked to Daftra (daftra_id) are refreshed — their name, price
and whether they are active. Daftra's other products are never added: the catalog is curated, and
Daftra's list is mostly unpriced placeholders and duplicate names. A Daftra product with no price
never clears ours.

Clients: the same full rebuild the nightly job runs (app.import_clients).

(Not to be confused with app.daftra_sync, which writes invoices to Daftra when a request is approved.)
"""

import threading
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import daftra
from .audit import Audit
from .database import SessionLocal, get_db
from .import_clients import replace_clients
from .models import AuditLog, Product, SyncRun, User
from .security import require_admin
from .text import squash

router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])

KINDS = {"products": "المنتجات", "clients": "العملاء"}
# A run still "running" after this long died with the server (a restart mid-run)
STALE_AFTER = timedelta(minutes=30)
HISTORY_LIMIT = 20


def _now():
    return datetime.now(timezone.utc)


def _price(raw) -> Decimal | None:
    try:
        price = Decimal(str(raw)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return price if price > 0 else None


# ---------- What each refresh does ----------

def sync_products(db: Session, actor: User | None, by_name: str) -> dict:
    """Refreshes name, price and active of the linked products from Daftra, in the caller's transaction."""
    remote = {int(product["id"]): product for product in daftra.list_products()}
    linked = db.scalars(select(Product).where(Product.daftra_id.is_not(None)).order_by(Product.name)).all()
    changed, missing, skipped = [], [], []
    unchanged = 0
    for product in linked:
        source = remote.get(product.daftra_id)
        if source is None:
            # Deleted in Daftra, or the link is wrong: reported, left as it is
            missing.append({"id": product.id, "name": product.name, "daftra_id": product.daftra_id})
            continue
        before, after = {}, {}

        name = squash(source.get("name"))
        if name and name != product.name:
            taken = db.scalar(select(Product).where(Product.name == name, Product.id != product.id))
            if taken is not None:
                skipped.append({"id": product.id, "name": product.name,
                                "reason": f"اسمه في دفترة «{name}» مستخدم لمنتج آخر في البوابة"})
            else:
                before["name"], after["name"] = product.name, name
                product.name = name

        price = _price(source.get("unit_price"))
        if price is not None and price != product.unit_price:
            before["unit_price"], after["unit_price"] = float(product.unit_price), float(price)
            product.unit_price = price

        active = str(source.get("deactivate") or "0") != "1"
        if active != product.is_active:
            before["is_active"], after["is_active"] = product.is_active, active
            product.is_active = active

        if not after and not any(item["id"] == product.id for item in skipped):
            unchanged += 1
        if after:
            changed.append({"id": product.id, "name": product.name, "before": before, "after": after})
            db.add(AuditLog(
                user_id=actor.id if actor else None, username=(actor.username if actor else by_name)[:50],
                action="product.daftra_sync", entity_type="product", entity_id=product.id,
                entity_label=product.name[:160], before=before, after=after,
            ))
        # Flushed one by one so the name check above sees the names already changed
        db.flush()
    return {
        "linked": len(linked), "changed": changed, "unchanged": unchanged,
        "missing": missing, "skipped": skipped,
    }


def sync_clients(db: Session, actor: User | None, by_name: str) -> dict:
    return replace_clients(db, daftra.list_clients())


SYNCS = {"products": sync_products, "clients": sync_clients}


# ---------- Running them ----------

def _execute(db: Session, run: SyncRun):
    """Runs one queued refresh and records how it ended; the refresh and its record commit together."""
    run.status = "running"
    run.started_at = _now()
    db.commit()
    actor = db.get(User, run.started_by_id) if run.started_by_id else None
    try:
        run.summary = SYNCS[run.kind](db, actor, run.started_by_name)
        run.status = "done"
    except Exception as error:  # noqa: BLE001 — whatever went wrong is shown on the page
        db.rollback()
        run = db.get(SyncRun, run.id)
        run.status = "failed"
        run.error = (str(error) or error.__class__.__name__)[:1000]
    run.finished_at = _now()
    db.commit()
    return run


def _run_queued(run_ids: list[int]):
    """Thread body: the runs one after the other, each in its own session."""
    for run_id in run_ids:
        with SessionLocal() as db:
            _execute(db, db.get(SyncRun, run_id))


def run_now(kind: str, by_name: str) -> SyncRun:
    """Runs a refresh in this process and waits for it (the nightly job)."""
    with SessionLocal() as db:
        run = SyncRun(kind=kind, status="queued", started_by_name=by_name)
        db.add(run)
        db.commit()
        return _execute(db, run)


def _busy(db: Session) -> list[SyncRun]:
    """Runs still queued or running. One that has been at it too long died with the server, and is closed."""
    runs = db.scalars(select(SyncRun).where(SyncRun.status.in_(("queued", "running")))).all()
    alive = []
    for run in runs:
        if _now() - run.started_at > STALE_AFTER:
            run.status, run.finished_at, run.error = "failed", _now(), "توقفت المزامنة قبل أن تنتهي (أُعيد تشغيل الخادم)"
        else:
            alive.append(run)
    db.commit()
    return alive


# ---------- API ----------

class SyncIn(BaseModel):
    kinds: list[str] = Field(min_length=1)


def run_out(run: SyncRun) -> dict:
    return {
        "id": run.id, "kind": run.kind, "label": KINDS.get(run.kind, run.kind), "status": run.status,
        "started_by": run.started_by_name, "started_at": run.started_at, "finished_at": run.finished_at,
        "summary": run.summary, "error": run.error,
    }


@router.get("/daftra-sync")
def sync_status(db: Session = Depends(get_db)):
    busy = {run.kind: run for run in _busy(db)}
    kinds = []
    for kind, label in KINDS.items():
        last = db.scalar(select(SyncRun).where(SyncRun.kind == kind, SyncRun.status.in_(("done", "failed")))
                         .order_by(SyncRun.id.desc()).limit(1))
        kinds.append({"key": kind, "label": label, "busy": run_out(busy[kind]) if kind in busy else None,
                      "last": run_out(last) if last else None})
    linked = db.scalar(select(Product.id).where(Product.daftra_id.is_not(None)).limit(1)) is not None
    history = db.scalars(select(SyncRun).order_by(SyncRun.id.desc()).limit(HISTORY_LIMIT)).all()
    return {"kinds": kinds, "has_linked_products": linked, "history": [run_out(run) for run in history]}


@router.post("/daftra-sync", status_code=status.HTTP_202_ACCEPTED)
def start_sync(body: SyncIn, admin: User = Depends(require_admin), audit: Audit = Depends(), db: Session = Depends(get_db)):
    kinds = [kind for kind in KINDS if kind in set(body.kinds)]
    if not kinds:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "اختر ما تريد مزامنته")
    if _busy(db):
        raise HTTPException(status.HTTP_409_CONFLICT, "توجد مزامنة قيد التشغيل؛ انتظر حتى تنتهي")
    runs = [SyncRun(kind=kind, status="queued", started_by_id=admin.id, started_by_name=admin.full_name or admin.username)
            for kind in kinds]
    db.add_all(runs)
    audit.log(admin, "daftra.sync", after={"kinds": [KINDS[kind] for kind in kinds]})
    db.commit()
    threading.Thread(target=_run_queued, args=([run.id for run in runs],), daemon=True).start()
    return {"runs": [run_out(run) for run in runs]}
