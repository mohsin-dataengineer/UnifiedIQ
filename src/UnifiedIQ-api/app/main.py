"""FastAPI application: lifespan, CORS, middleware, exception model, routers."""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.deps import build_state
from app.errors import BAD_REQUEST, INTERNAL, AppError
from app.integrations.email_smtp import EmailIntegration
from app.integrations.slack import SlackIntegration
from app.observability import configure_logging, setup_telemetry
from app.routers import (
    alerts,
    canvases,
    chat,
    health,
    integrations,
    memory,
    verify,
    views,
)
from app.workers import start_workers, stop_workers

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    state = build_state(settings)
    app.state.app_state = state
    setup_telemetry(app)
    start_workers(state)
    state.registry.register(SlackIntegration(settings, state.http))
    state.registry.register(EmailIntegration(settings))
    state.registry.register(state.in_app)
    if settings.alerts_enabled:
        try:
            await state.alerts.ensure_table()
        except Exception:  # noqa: BLE001 - app still serves without alerts
            logger.exception("alert table init failed")
    try:
        await state.canvases.ensure_table()
    except Exception:  # noqa: BLE001 - canvas listing is best-effort
        logger.exception("canvases table init failed")
    try:
        await state.views.ensure_table()
    except Exception:  # noqa: BLE001 - dashboard pinning is best-effort
        logger.exception("views table init failed")
    try:
        await state.views.backfill_canvas_ids()
    except Exception:  # noqa: BLE001 - migration is best-effort
        logger.exception("views canvas_id backfill failed")
    try:
        await state.user_memory.ensure_table()
    except Exception:  # noqa: BLE001 - chat works without user memory
        logger.exception("user_memory table init failed")
    try:
        yield
    finally:
        await stop_workers(state)
        await state.http.aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        latency_ms = int((time.perf_counter() - started) * 1000)
        response.headers["x-request-id"] = request_id
        logger.info(
            "request",
            extra={
                "request_id": request_id,
                "user_email": request.headers.get("x-user-email"),
                "latency_ms": latency_ms,
            },
        )
        return response

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "code": BAD_REQUEST,
                "message": "Request validation failed",
                "request_id": getattr(request.state, "request_id", None),
                "errors": exc.errors(),
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error")
        return JSONResponse(
            status_code=500,
            content={
                "code": INTERNAL,
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    app.include_router(health.router)
    app.include_router(chat.router)
    app.include_router(verify.router)
    app.include_router(integrations.router)
    app.include_router(alerts.router)
    app.include_router(views.router)
    app.include_router(canvases.router)
    app.include_router(memory.router)

    # Serve the prebuilt static UI (Next.js static export) if present.
    # Mounted last so /api/* and /docs resolve first; html=True gives SPA
    # fallback so client-side routes return index.html.
    static_dir = Path(__file__).resolve().parent.parent / "static"
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="ui")

    return app


app = create_app()
