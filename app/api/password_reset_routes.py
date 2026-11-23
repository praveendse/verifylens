"""Self-service password recovery by email link (docs/specs/password-recovery.md)."""
import logging
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
from app.db.database import get_session, get_session_factory
from app.dto.auth_models import PasswordResetConfirm, PasswordResetRequest
from app.services import password_reset_service as svc
from app.services.mail_service import MailSender
from app.settings import Settings
from security.password_policy import password_problem
from security.passwords import hash_password

router = APIRouter(prefix="/auth/password-reset", tags=["Authentication"])
logger = logging.getLogger(__name__)

REQUEST_ACCEPTED = "If an account matches, we've sent a link to reset the password. Check your email."
INVALID_LINK = "Invalid or expired reset link"
RESET_DONE = "Password updated. Please sign in with your new password."


def require_reset_available(settings: Annotated[Settings, Depends(get_settings)]) -> None:
    if not svc.is_available(settings):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")


@router.get("/status")
def reset_status(settings: Annotated[Settings, Depends(get_settings)]):
    """Lets the sign-in page decide whether to show "Forgot password?"."""
    return {"enabled": svc.is_available(settings)}


def _process_request(
    identifier: str,
    ip: str,
    settings: Settings,
    mailer: MailSender,
    session_factory: Callable[[], Session],
) -> None:
    """Runs after the response is sent, so the response looks and times the
    same whether or not an account matches. Never logs the token or link."""
    try:
        with session_factory() as session:
            user = svc.find_user(session, identifier)
            if user is None or not user.is_active or not user.email:
                logger.info("Password reset requested (ip=%s): no eligible account", ip)
                return
            # Counted per account, so username and email share one limit.
            if reset_request_account_limiter.hit(f"user:{user.id}") is not None:
                logger.warning("Password reset over the per-account limit (user_id=%s, ip=%s); no email sent",
                               user.id, ip)
                return
            minutes = settings.password_reset_token_minutes
            raw = svc.issue_token(session, user, ip, minutes)
            to, uid = user.email, user.id
        subject, body = svc.reset_email(svc.reset_link(settings.app_base_url, raw), minutes)
        mailer.send(to, subject, body)
        logger.info("Password reset link sent (user_id=%s, ip=%s)", uid, ip)
    except Exception as exc:  # noqa: BLE001 - background task: log, never raise
        logger.warning("Password reset request failed (ip=%s): %s", ip, type(exc).__name__)


def _send_changed_notice(mailer: MailSender, to: str, uid: int) -> None:
    try:
        mailer.send(to, *svc.changed_email())
    except Exception as exc:  # noqa: BLE001
        logger.warning("Password changed notice failed (user_id=%s): %s", uid, type(exc).__name__)


@router.post(
    "/request",
    status_code=status.HTTP_202_ACCEPTED,
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
    background.add_task(_process_request, payload.identifier, client_ip(request), settings, mailer, session_factory)
    return {"detail": REQUEST_ACCEPTED}


@router.post(
    "/confirm",
    dependencies=[Depends(require_reset_available), Depends(limit_reset_confirm)],
)
def confirm_reset(
    payload: PasswordResetConfirm,
    request: Request,
    background: BackgroundTasks,
    session: Annotated[Session, Depends(get_session)],
    mailer: Annotated[MailSender, Depends(get_mail_sender)],
):
    ip = client_ip(request)
    now = svc.utcnow()
    found = svc.find_valid_token(session, payload.token, now)
    if found is None:
        logger.info("Password reset confirm rejected (ip=%s): invalid or expired link", ip)
        raise HTTPException(status_code=400, detail=INVALID_LINK)
    row, user = found

    # Checked before the token is used up, so the user can retry with a better password.
    problem = password_problem(user.username, payload.new_password)
    if problem:
        raise HTTPException(status_code=422, detail=problem)

    if not svc.claim_token(session, row.id, now):
        session.rollback()
        raise HTTPException(status_code=400, detail=INVALID_LINK)
    user.hashed_password = hash_password(payload.new_password)
    user.must_change_password = False
    user.token_version += 1  # signs out every existing session
    svc.cancel_unused_tokens(session, user.id, now)
    session.add(user)
    session.commit()
    logger.info("Password reset completed (user_id=%s, ip=%s)", user.id, ip)

    if user.email:
        background.add_task(_send_changed_notice, mailer, user.email, user.id)
    return {"detail": RESET_DONE}
