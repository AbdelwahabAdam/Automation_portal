"""requests' HTTP routes, split by screen. Each file is still the transport layer."""

from fastapi import APIRouter

from . import attachments, requests, review

router = APIRouter()
router.include_router(requests.router)
router.include_router(attachments.router)
router.include_router(review.router)
