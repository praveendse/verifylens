from fastapi import APIRouter, Depends

from app.api.auth_dependencies import get_current_user
from app.api.dependencies import get_health_service
from app.dto.models import HealthResponse, SystemStatusResponse
from app.services.health_service import SystemHealthService

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:

    return HealthResponse(
        status="ok",
        message="Wikipedia Verification API is running",
    )

@router.get("/health/systems", response_model=SystemStatusResponse)
def system_status(
    _user=Depends(get_current_user),  # signed-in users only: dependency status is internal info
    health: SystemHealthService = Depends(get_health_service),
) -> SystemStatusResponse:
    """Live check of API, database, Gemini and Wikipedia (external checks cached 60s)."""
    return health.status()


# The legacy Task 02 route GET /report was removed: it ran the full
# Wikipedia + Gemini pipeline without authentication and without recording
# search history. Use the authenticated POST /search instead.
