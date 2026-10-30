"""What a job run is recorded as.

One row per run of any job, whoever started it: the nightly cron, the «المزامنة مع دفترة» admin
page, or a command line. It replaces `sync_runs`, which only knew about the two Daftra lists;
the migration copies that history across.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base


class JobRun(Base):
    """One run of one job, with what it changed (summary) or why it failed."""

    __tablename__ = "job_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    # The job's registered name, e.g. "sync_clients" (see jobs/registry.py)
    name: Mapped[str] = mapped_column(String(40), index=True)
    # queued -> running -> done | failed
    status: Mapped[str] = mapped_column(String(10))
    started_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    # Name at the time (or «المزامنة الليلية»), kept if the user is later deleted
    started_by_name: Mapped[str] = mapped_column(String(120), default="", server_default="")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    summary: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str] = mapped_column(Text, default="", server_default="")
