"""Messenger API 엔트리포인트."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api import auth, conversations, files, health, users, ws
from app.core.config import FORBIDDEN_JWT_SECRETS, settings
from app.core.logging_config import setup_logging
from app.core.rate_limit import limiter
from app.middleware.request_context import RequestContextMiddleware

setup_logging()
log = logging.getLogger("app")

os.makedirs(settings.upload_dir, exist_ok=True)
os.makedirs(os.path.join(settings.upload_dir, "temp"), exist_ok=True)
os.makedirs(os.path.join(settings.upload_dir, "final"), exist_ok=True)
os.makedirs(os.path.join(settings.upload_dir, "avatars"), exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.environment == "development" and settings.jwt_secret in FORBIDDEN_JWT_SECRETS:
        log.warning("JWT_SECRET is a documented placeholder; set a strong secret before production")
    yield


app = FastAPI(title="Messenger API", version="0.1.0", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

if settings.trusted_host_list:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_host_list)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestContextMiddleware)

app.include_router(health.router)
app.include_router(auth.router, prefix="/auth")
app.include_router(users.router)
app.include_router(conversations.router)
app.include_router(files.router)
app.include_router(ws.router)

if settings.metrics_enabled:
    Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
