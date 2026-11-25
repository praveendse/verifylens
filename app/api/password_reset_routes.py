"""Self-service password recovery by email link (docs/specs/password-recovery.md)."""
from typing import Annotated, Callable

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlmodel import Session

from app.api.dependencies import get_mail_sender, get_settings
from app.api.rate_limit import (
    client_ip,
    limit_reset_confirm,
    limit_reset_request,
    reset_request_account_limiter,
)
from app.infra.db.database import get_session, get_session_factory
from app.dto.auth_models import PasswordResetConfirm, PasswordResetRequest, ResetAvailability
from app.dto.common import MessageResponse
from app.services import password_reset_service as svc
from app.services.mail_service import MailSender
from app.config import Settings

router = APIRouter(prefix="/auth/password-reset", tags=["Authentication"])

REQUEST_ACCEPTED = "If an account matches, we've sent a link to reset the password. Check your email."
INVALID_LINK = "Invalid or expired reset link"
RESET_DONE = "Password updated. Please sign in with your new password."


def require_reset_available(settings: Annotated[Settings, Depends(get_settings)]) -> None:
    if not svc.is_available(settings):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")


@router.get("/status", response_model=ResetAvailability)
def reset_status(settings: Annotated[Settings, Depends(get_settings)]):
    """Lets the sign-in page decide whether to show "Forgot password?"."""
    return ResetAvailability(enabled=svc.is_available(settings))


@router.post(
    "/request",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=MessageResponse,
    dependencies=[Depends(require_reset_available), Depends(limit_reset_request)],
)
def request_reset(
    payload: PasswordResetRequest,
    request: Request,
    background: BackgroundTasks,
    settings: Annotated[Settings, Depends(get_settings)],
    mailer: Annotated[MailSender, Depends(get_mail_sender)],
    session_factory: Annotated[Callable[[], Session], Depends(get_session_factory)],
):
    background.add_task(
        svc.process_reset_request, payload.identifier, client_ip(request), settings, mailer, session_factory,
        reset_request_account_limiter.hit,
    )
    return MessageResponse(detail=REQUEST_ACCEPTED)


@router.post(
    "/confirm",
    response_model=MessageResponse,
    dependencies=[Depends(require_reset_available), Depends(limit_reset_confirm)],
)
def confirm_reset(
    payload: PasswordResetConfirm,
    request: Request,
    background: BackgroundTasks,
    session: Annotated[Session, Depends(get_session)],
    mailer: Annotated[MailSender, Depends(get_mail_sender)],
):
    try:
        user = svc.confirm_reset(session, payload.token, payload.new_password, client_ip(request))
    except svc.InvalidResetLinkError:
        raise HTTPException(status_code=400, detail=INVALID_LINK) from None
    except svc.WeakPasswordError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    if user.email:
        background.add_task(svc.send_changed_notice, mailer, user.email, user.id)
    return MessageResponse(detail=RESET_DONE)
