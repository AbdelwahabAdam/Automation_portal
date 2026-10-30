"""identity's HTTP routes, split by screen. Each file is still the transport layer."""

from fastapi import APIRouter

from . import account, auth, users

router = APIRouter()
router.include_router(auth.router)
router.include_router(account.router)
router.include_router(users.router)
