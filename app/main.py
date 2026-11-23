import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from security.secrets import validate_secrets
from app.db.database import engine
from app.db.migrations import upgrade_schema
from app.api.routes import router
from app.frontend import mount_frontend
from app.settings import Settings
from app.api.search_routes import router as search_router
from app.api.history_routes import router as history_router
from app.api.auth_routes import router as auth_router
from app.api.user_routes import router as user_router
from app.api.admin_routes import router as admin_router
from app.api.password_reset_routes import router as password_reset_router
from app.services.password_reset_service import config_problem, purge_old_tokens


settings = Settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    validate_secrets()  # refuse to start with a missing/weak JWT secret
    upgrade_schema(engine)  # additive only: creates missing tables/columns
    purge_old_tokens(engine)  # PWR-16: drop reset tokens used/expired > 7 days ago
    problem = config_problem(Settings())
    if problem:
        logger.warning(problem)  # PWR-15: feature stays off until fixed
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(
    router,
    prefix="/api/v1",
)

app.include_router(
    search_router, 
    prefix="/api/v1"
)

app.include_router(
    history_router, 
    prefix="/api/v1"
)

app.include_router(
    auth_router, 
    prefix="/api/v1"
)

app.include_router(
    user_router,
    prefix="/api/v1",
)

app.include_router(
    admin_router,
    prefix="/api/v1",
)

app.include_router(
    password_reset_router,
    prefix="/api/v1",
)

# Keep last: its catch-all route must not shadow the API routes above.
mount_frontend(app, settings.frontend_dist)