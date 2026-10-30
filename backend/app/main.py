"""The portal's API. Each part lives in its own module; this one puts them together and starts up.

- auth: logging in and out, two-step codes, password links
- requests_api: a salesperson's requests and their attachments
- lookups: clients, our catalog and Daftra's lists, for the sales forms
- review: managers approving or returning requests (and creating the Daftra documents)
- account: the signed-in user's own page
- admin, catalog: the admin pages
"""

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

from . import (account, admin, auth, catalog, daftra_refresh, import_client_categories, lookups, order_sources,
               requests_api, review)
from .integrations import daftra
from .core.config import settings
from .core.errors import DomainError
from .core.database import SessionLocal, run_migrations
from .models import ClientCategory

log = logging.getLogger(__name__)
# Below this, the secret that signs logins is guessable (HS256 wants at least 32 bytes)
MIN_SECRET_BYTES = 32


@asynccontextmanager
async def lifespan(app: FastAPI):
    if len(settings.jwt_secret.encode()) < MIN_SECRET_BYTES:
        log.warning("JWT_SECRET is shorter than %s bytes; set a long random one in .env", MIN_SECRET_BYTES)
    run_migrations()
    # Loading the Daftra lists takes several seconds, so start before the first user asks
    threading.Thread(target=warm_daftra_lists, daemon=True).start()
    yield


def warm_daftra_lists():
    for load in (daftra.list_staff_members, daftra.list_treasuries, daftra.list_order_sources):
        try:
            load()
        except daftra.DaftraError:
            pass
    # The client categories live in our database; they are copied from Daftra only the first time
    # (run app.import_client_categories to refresh them)
    with SessionLocal() as db:
        empty = db.scalar(select(func.count()).select_from(ClientCategory)) == 0
    if empty:
        try:
            import_client_categories.import_categories()
        except daftra.DaftraError:
            pass


app = FastAPI(title="FutureLife Portal", lifespan=lifespan)


@app.exception_handler(DomainError)
async def domain_error(request: Request, error: DomainError) -> JSONResponse:
    """A service's error, answered exactly as the routes answered it before."""
    return JSONResponse({"detail": error.body()}, status_code=error.status_code)


for module in (auth, requests_api, lookups, review, account, admin, catalog, daftra_refresh, order_sources):
    app.include_router(module.router)
