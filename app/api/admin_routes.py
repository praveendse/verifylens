"""Admin overview: the numbers behind the Admin > Overview tab."""
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.api.auth_dependencies import require_admin
from app.dto.admin_models import AdminOverviewResponse
from app.infra.db.database import get_session
from app.infra.db.models import User
from app.services import admin_service

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/overview", response_model=AdminOverviewResponse)
def admin_overview(
    admin: Annotated[User, Depends(require_admin)],
    session: Annotated[Session, Depends(get_session)],
):
    return admin_service.get_admin_overview(session)
