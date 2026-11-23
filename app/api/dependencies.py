from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.settings import Settings
from app.services.health_service import SystemHealthService
from app.services.mail_service import MailSender, SmtpMailSender
from app.services.pipeline_service import PipelineService


def get_settings() -> Settings:
    return Settings()


def get_mail_sender(settings: Annotated[Settings, Depends(get_settings)]) -> MailSender:
    return SmtpMailSender(settings)


def get_pipeline_service() -> PipelineService:
    settings = Settings()

    return PipelineService(settings=settings)


@lru_cache(maxsize=1)
def get_health_service() -> SystemHealthService:
    # Single shared instance so the external-check cache is shared across requests.
    return SystemHealthService(settings=Settings())
