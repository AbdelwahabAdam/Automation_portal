"""Which version of the portal is answering."""

from fastapi import APIRouter, Depends

from ...core.config import settings
from ...core.security import require_admin

router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])


@router.get("/version")
def running_version():
    """Which version of the portal is answering: the number, the build, and what it was built from."""
    return {
        "version": settings.app_version,
        "build": settings.app_build,
        "commit": settings.app_commit,
        "built_at": settings.app_built_at,
    }
