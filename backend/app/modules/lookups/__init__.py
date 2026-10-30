"""Daftra's lists the forms pick from: its staff, its treasuries and its order sources.

The «مصادر الطلب» admin page is here too. Our own copy of Daftra's client categories belongs to
`clients`, which owns that table.
"""

from fastapi import APIRouter

from .router import admin_router
from .router import router as forms_router
from .service import from_daftra, order_sources, staff, staff_members, treasuries

router = APIRouter()
router.include_router(forms_router)
router.include_router(admin_router)

__all__ = ["from_daftra", "order_sources", "router", "staff", "staff_members", "treasuries"]
