"""Running a job and recording the run.

Three ways in, one path: `run_now` for the cron and the command line (in this process, waits for
it), `start_in_background` for the admin page (a thread, so the page answers at once). Either
way the run goes through `_execute`, so every run is recorded the same.
"""

import threading
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.context import SYSTEM_LABEL, Actor
from ..core.database import SessionLocal
from .models import JobRun
from .registry import get

# A run still "running" after this long died with the server (a restart mid-run)
STALE_AFTER = timedelta(minutes=30)
STALE_MESSAGE = "توقفت المزامنة قبل أن تنتهي (أُعيد تشغيل الخادم)"


def _now():
    return datetime.now(timezone.utc)


def _execute(db: Session, run: JobRun) -> JobRun:
    """Runs one queued job and records how it ended; the work and its record commit together."""
    run.status = "running"
    run.started_at = _now()
    db.commit()
    who = Actor(user=db.get(_user_model(), run.started_by_id) if run.started_by_id else None,
                username=run.started_by_name)
    try:
        run.summary = get(run.name).run(db, who)
        run.status = "done"
    except Exception as error:          # noqa: BLE001 — whatever went wrong is shown on the page
        db.rollback()
        run = db.get(JobRun, run.id)
        run.status = "failed"
        run.error = (str(error) or error.__class__.__name__)[:1000]
    run.finished_at = _now()
    db.commit()
    return run


def _user_model():
    # Imported here, not at the top: jobs sit above the modules and this is the one thing a run
    # needs from identity — who started it.
    from ..modules.identity import User

    return User


def queue(db: Session, name: str, by_name: str = SYSTEM_LABEL, by_id: int | None = None) -> JobRun:
    run = JobRun(name=name, status="queued", started_by_id=by_id, started_by_name=by_name)
    db.add(run)
    return run


def run_now(name: str, by_name: str = SYSTEM_LABEL) -> JobRun:
    """Runs a job in this process and waits for it (the cron and the command line)."""
    with SessionLocal() as db:
        run = queue(db, name, by_name)
        db.commit()
        return _execute(db, run)


def _run_queued(run_ids: list[int]):
    """Thread body: the runs one after the other, each in its own session."""
    for run_id in run_ids:
        with SessionLocal() as db:
            _execute(db, db.get(JobRun, run_id))


def start_in_background(run_ids: list[int]):
    threading.Thread(target=_run_queued, args=(run_ids,), daemon=True).start()


def busy(db: Session) -> list[JobRun]:
    """Runs still queued or running. One that has been at it too long died with the server, and
    is closed, so the page is not stuck saying a sync is running."""
    runs = db.scalars(select(JobRun).where(JobRun.status.in_(("queued", "running")))).all()
    alive = []
    for run in runs:
        if _now() - run.started_at > STALE_AFTER:
            run.status, run.finished_at, run.error = "failed", _now(), STALE_MESSAGE
        else:
            alive.append(run)
    db.commit()
    return alive


def last_run(db: Session, name: str) -> JobRun | None:
    return db.scalar(
        select(JobRun).where(JobRun.name == name, JobRun.status.in_(("done", "failed")))
        .order_by(JobRun.id.desc()).limit(1)
    )


def history(db: Session, limit: int) -> list[JobRun]:
    return list(db.scalars(select(JobRun).order_by(JobRun.id.desc()).limit(limit)))
