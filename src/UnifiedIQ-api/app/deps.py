"""Application state container and FastAPI dependencies.

Services are instantiated once per process in the lifespan and hung off
`app.state`. Dependencies just read them back — no per-request construction.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx
from fastapi import Depends, Request

from app.config import Settings, get_settings
from app.integrations.in_app import InAppIntegration
from app.models.domain import CurrentUser
from app.services.alerts import AlertScheduler, AlertService
from app.services.auth import ServiceAuthService, UserAuthService
from app.services.cache import CacheService
from app.services.integration_registry import IntegrationRegistry
from app.services.llm import LLMService
from app.services.session_store import SessionStore
from app.services.telemetry import TelemetryLogger
from app.services.warehouse import DatabricksWarehouse, WarehouseService


@dataclass
class AppState:
    settings: Settings
    http: httpx.AsyncClient
    llm: LLMService
    warehouse: WarehouseService
    cache: CacheService
    sessions: SessionStore
    telemetry: TelemetryLogger
    registry: IntegrationRegistry
    user_auth: UserAuthService
    service_auth: ServiceAuthService
    in_app: InAppIntegration
    alerts: AlertService
    alert_scheduler: AlertScheduler


def build_state(settings: Settings) -> AppState:
    http = httpx.AsyncClient(timeout=30.0)
    warehouse = DatabricksWarehouse(settings)
    registry = IntegrationRegistry()
    in_app = InAppIntegration(settings)
    alerts = AlertService(settings, warehouse, registry)
    return AppState(
        settings=settings,
        http=http,
        llm=LLMService(settings),
        warehouse=warehouse,
        cache=CacheService(maxsize=settings.cache_max_size, ttl=settings.cache_ttl_seconds),
        sessions=SessionStore(settings),
        telemetry=TelemetryLogger(settings),
        registry=registry,
        user_auth=UserAuthService(settings, http),
        service_auth=ServiceAuthService(settings),
        in_app=in_app,
        alerts=alerts,
        alert_scheduler=AlertScheduler(settings, alerts),
    )


def get_state(request: Request) -> AppState:
    return request.app.state.app_state


async def get_current_user(request: Request, state: AppState = Depends(get_state)) -> CurrentUser:
    auth_header = request.headers.get("authorization", "")
    bearer = auth_header.split(" ", 1)[1] if auth_header.lower().startswith("bearer ") else None
    return await state.user_auth.authenticate(
        bearer,
        header_email=request.headers.get("x-user-email"),
        header_name=request.headers.get("x-user-name"),
        forwarded_email=request.headers.get("x-forwarded-email"),
        forwarded_user=request.headers.get("x-forwarded-preferred-username"),
    )


def settings_dep() -> Settings:
    return get_settings()
