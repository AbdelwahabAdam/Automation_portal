"""The portal's API. Each part lives in its own module; this one puts them together and starts up.

- forms: every form, one folder each; importing it registers them all
- jobs: the nightly sync, the admin page's buttons and the command-line imports
- identity: logging in and out, two-step codes, password links, the account and users screens
- clients, catalog, lookups: what the forms look things up in
- requests: a salesperson's requests, their files, and the managers' review
- catalog: the products and packages page
"""

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from . import forms, jobs
from .modules import (audit, catalog, clients, form_engine, identity, lookups, notifications, requests,
                      system)
from .core.config import settings
from .core.context import Actor
from .core.errors import DomainError
from .core.permissions import declare_admin_pages
from .core.database import SessionLocal, run_migrations

log = logging.getLogger(__name__)
# Below this, the secret that signs logins is guessable (HS256 wants at least 32 bytes)
MIN_SECRET_BYTES = 32
# The fake Daftra account is for a developer's machine. On the server every approval would look
# successful with no invoice behind it, so a real version refuses to start with it on.
DEV_VERSION = "dev"


def _warm_up():
    """Loading Daftra's lists takes several seconds, so it starts before the first user asks."""
    with SessionLocal() as db:
        # The fake only knows the clients, products and staff the database knows, so it is filled
        # from it first: otherwise approving for an existing client fails against an empty account
        if settings.daftra_fake:
            try:
                jobs.fake_daftra.seed()
            except Exception:              # noqa: BLE001 — a local convenience, never a reason not to start
                log.exception("Could not seed the fake Daftra account")
        try:
            jobs.get("warm_daftra_cache").run(db, Actor.system())
        except Exception:                  # noqa: BLE001 — the lists load again on the first ask
            log.exception("Could not warm Daftra's lists")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if len(settings.jwt_secret.encode()) < MIN_SECRET_BYTES:
        log.warning("JWT_SECRET is shorter than %s bytes; set a long random one in .env", MIN_SECRET_BYTES)
    if settings.daftra_fake:
        if settings.app_version != DEV_VERSION:
            raise RuntimeError(
                f"DAFTRA_FAKE is on and this is version {settings.app_version}, not {DEV_VERSION}. "
                "Nothing would reach Daftra while every approval looked successful. "
                "Set DAFTRA_FAKE=false (the production compose file hard-codes it off)."
            )
        log.warning("DAFTRA_FAKE is on: nothing reaches Daftra. Every invoice, receipt and work "
                    "order is made up inside the portal.")
    # Importing app.forms registered them; say how many, so a folder that failed to load shows
    log.info("%s form folders loaded, %s forms registered", len(forms.FORMS), len(form_engine.all_forms()))
    run_migrations()
    # Loading the Daftra lists takes several seconds, so start before the first user asks
    threading.Thread(target=_warm_up, daemon=True).start()
    yield


# Every admin page's own permission; the forms declared theirs as they registered
declare_admin_pages()

app = FastAPI(title="FutureLife Portal", lifespan=lifespan)


@app.exception_handler(DomainError)
async def domain_error(request: Request, error: DomainError) -> JSONResponse:
    """A service's error, answered exactly as the routes answered it before."""
    return JSONResponse({"detail": error.body()}, status_code=error.status_code)


for module in (identity, requests, clients, lookups, catalog, jobs,
               audit, notifications, system):
    app.include_router(module.router)
