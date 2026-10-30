"""The one way to run a job from a command line.

    python -m app.jobs --list                             what there is
    python -m app.jobs sync_clients                       run it, recorded in job_runs
    python -m app.jobs sync_clients /imports/clients.json  a job's own arguments are passed on

A job with a `main` of its own (the imports, which take files and options) gets the remaining
arguments; the rest are run through the runner, which records the run.
"""

import inspect
import sys

from . import registry
from .runner import run_now


def _list() -> int:
    width = max(len(job.name) for job in registry.all_jobs())
    for job in sorted(registry.all_jobs(), key=lambda j: j.name):
        where = " (admin page)" if job.on_admin_page else ""
        print(f"  {job.name:<{width}}  {job.label}{where}")
        if job.about:
            print(f"  {'':<{width}}  {job.about}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("--list", "-l", "--help", "-h"):
        if not argv or argv[0] in ("--list", "-l"):
            return _list()
        print(__doc__)
        return 0

    name, rest = argv[0], argv[1:]
    job = registry.find(name)
    if job is None:
        print(f"No job called {name!r}. Try --list.", file=sys.stderr)
        return 2

    # A job that takes arguments of its own runs its own command line. Some read sys.argv with
    # argparse and take nothing, so they are given the arguments that way.
    own_main = getattr(sys.modules[job.run.__module__], "main", None)
    if own_main is not None:
        if inspect.signature(own_main).parameters:
            return own_main(rest) or 0
        sys.argv = [f"python -m app.jobs {name}", *rest]
        return own_main() or 0

    if rest:
        print(f"{name} takes no arguments", file=sys.stderr)
        return 2
    from ..core.database import run_migrations

    run_migrations()
    run = run_now(name)
    if run.status != "done":
        print(f"{name} failed: {run.error}", file=sys.stderr)
        return 1
    print(f"{name}: {run.summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
