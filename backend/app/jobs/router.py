"""The «المزامنة مع دفترة» admin page: what each list's last refresh did, and starting another.

The page shows the jobs marked `on_admin_page`. Starting one queues it and answers at once; the
run itself happens in a thread, and the page polls this for how it is going.
"""

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core.context import Actor
from ..core.database import get_db
from ..core.errors import Conflict, Invalid
from ..core.security import acting, require
from ..modules import catalog
from ..modules.audit import log as audit_log
from . import registry, runner

may_sync = require("admin.sync")
router = APIRouter(prefix="/api/admin", dependencies=[Depends(may_sync)])

HISTORY_LIMIT = 20
# The page's own words for the two jobs it offers. Kept as they were so the screen and the
# answers do not change with the jobs' names.
PAGE_KINDS = {"products": "sync_products", "clients": "sync_clients"}
JOB_KINDS = {job: kind for kind, job in PAGE_KINDS.items()}


class SyncIn(BaseModel):
    kinds: list[str] = Field(min_length=1)


def run_out(run) -> dict:
    job = registry.find(run.name)
    return {
        "id": run.id, "kind": JOB_KINDS.get(run.name, run.name),
        "label": job.label if job else run.name, "status": run.status,
        "started_by": run.started_by_name, "started_at": run.started_at, "finished_at": run.finished_at,
        "summary": run.summary, "error": run.error,
    }


@router.get("/daftra-sync")
def sync_status(db: Session = Depends(get_db)):
    busy = {run.name: run for run in runner.busy(db)}
    kinds = []
    for kind, name in PAGE_KINDS.items():
        job = registry.get(name)
        last = runner.last_run(db, name)
        kinds.append({"key": kind, "label": job.label,
                      "busy": run_out(busy[name]) if name in busy else None,
                      "last": run_out(last) if last else None})
    return {
        "kinds": kinds,
        "has_linked_products": catalog.has_linked_products(db),
        "history": [run_out(run) for run in runner.history(db, HISTORY_LIMIT)],
    }


@router.post("/daftra-sync", status_code=status.HTTP_202_ACCEPTED)
def start_sync(body: SyncIn, who: Actor = Depends(acting(may_sync)), db: Session = Depends(get_db)):
    chosen = set(body.kinds)
    wanted = [name for kind, name in PAGE_KINDS.items() if kind in chosen]
    if not wanted:
        raise Invalid("اختر ما تريد مزامنته")
    if runner.busy(db):
        raise Conflict("توجد مزامنة قيد التشغيل؛ انتظر حتى تنتهي")
    admin = who.user
    runs = [runner.queue(db, name, by_name=admin.full_name or admin.username, by_id=admin.id)
            for name in wanted]
    audit_log(db, who, "daftra.sync",
              after={"kinds": [registry.get(name).label for name in wanted]})
    db.commit()
    runner.start_in_background([run.id for run in runs])
    return {"runs": [run_out(run) for run in runs]}
