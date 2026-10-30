"""Where the jobs put themselves.

A job is a function with a name. It holds no business rules of its own: it calls a module's
service, so the admin page, the nightly cron and the command line all run the same code.

    @job("sync_clients", label="العملاء", on_admin_page=True)
    def sync_clients(db, who):
        return clients.sync_from_daftra(db, ...)
"""

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Job:
    name: str
    run: Callable
    label: str
    #: Shown on the «المزامنة مع دفترة» page, with a button to start it
    on_admin_page: bool = False
    #: Recorded in job_runs. False for the startup cache warm-up, which is not worth a row.
    recorded: bool = True
    #: One line for `python -m app.jobs --list`
    about: str = ""


_jobs: dict[str, Job] = {}


def job(name: str, label: str = "", on_admin_page: bool = False, recorded: bool = True, about: str = ""):
    """Registers the function below it as a job."""

    def register(run: Callable) -> Callable:
        if name in _jobs:
            raise ValueError(f"two jobs are registered as {name!r}")
        _jobs[name] = Job(name=name, run=run, label=label or name, on_admin_page=on_admin_page,
                          recorded=recorded, about=about or (run.__doc__ or "").strip().split("\n")[0])
        return run

    return register


def get(name: str) -> Job:
    return _jobs[name]


def find(name: str) -> Job | None:
    return _jobs.get(name)


def all_jobs() -> list[Job]:
    return list(_jobs.values())


def on_admin_page() -> list[Job]:
    return [j for j in _jobs.values() if j.on_admin_page]


def names() -> list[str]:
    return list(_jobs)
