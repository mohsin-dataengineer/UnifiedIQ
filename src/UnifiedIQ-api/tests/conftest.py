from __future__ import annotations

from typing import Any

import httpx
import pytest
from app.config import Settings
from app.deps import AppState, get_current_user, get_state
from app.integrations.in_app import InAppIntegration
from app.main import create_app
from app.models.domain import Alert, CurrentUser
from app.models.responses import AlertSpec, SQLGenerationResponse
from app.services.alerts import AlertScheduler
from app.services.auth import ServiceAuthService, UserAuthService
from app.services.cache import CacheService
from app.services.integration_registry import IntegrationRegistry
from app.services.session_store import SessionStore
from app.services.telemetry import TelemetryLogger


class FakeLLM:
    def __init__(self) -> None:
        self.plan = SQLGenerationResponse(
            intent="data",
            sql="SELECT region, revenue FROM sales",
            assumptions=["assumed current fiscal year"],
        )
        self.summary = "Revenue is highest in the West region."
        self.alert = AlertSpec(
            title="Low signups",
            metric_sql="SELECT COUNT(*) AS v FROM signups",
            comparator="lt",
            threshold=1000,
            channel="in_app",
            cadence_minutes=60,
        )

    async def chat_structured(
        self, messages: Any, response_model: Any, **kwargs: Any
    ) -> tuple[Any, Any]:
        if response_model is AlertSpec:
            return self.alert, {"usage": {}}
        return self.plan, {"usage": {}}

    async def chat(self, messages: Any, **kwargs: Any) -> str:
        return self.summary

    async def stream(self, messages: Any, **kwargs: Any):
        for token in self.summary.split(" "):
            yield token + " "


class FakeWarehouse:
    def __init__(self) -> None:
        self.rows = [
            {"region": "West", "revenue": 120},
            {"region": "East", "revenue": 90},
        ]

    async def execute(self, sql: str, *, params: Any = None) -> list[dict]:
        return self.rows

    async def execute_to_arrow(self, sql: str):  # noqa: ANN201
        raise NotImplementedError

    async def health(self) -> bool:
        return True


class FakeAlertService:
    def __init__(self, in_app: InAppIntegration) -> None:
        self._in_app = in_app
        self._alerts: dict[str, Alert] = {}

    async def ensure_table(self) -> None:
        return None

    async def create(self, user_email, nl, spec) -> Alert:  # noqa: ANN001
        import uuid

        a = Alert(
            id=uuid.uuid4().hex,
            user_email=user_email,
            title=spec.title,
            natural_language=nl,
            metric_sql=spec.metric_sql or "",
            comparator=spec.comparator or "lt",
            threshold=float(spec.threshold or 0),
            channel=spec.channel,
            recipient=spec.recipient,
            cadence_minutes=spec.cadence_minutes,
        )
        self._alerts[a.id] = a
        return a

    async def list(self, user_email) -> list[Alert]:  # noqa: ANN001
        return [a for a in self._alerts.values() if a.user_email == user_email]

    async def delete(self, user_email, alert_id) -> None:  # noqa: ANN001
        self._alerts.pop(alert_id, None)

    async def run_now(self, user_email, alert_id) -> Alert | None:  # noqa: ANN001
        a = self._alerts.get(alert_id)
        if a is None:
            return None
        a.last_state = "breached"
        a.last_value = 1.0
        await self._in_app.execute(
            "notify",
            {
                "user_email": user_email,
                "title": a.title,
                "message": "breached",
            },
            ctx=await self._in_app.authenticate(None),
        )
        return a


@pytest.fixture
def settings() -> Settings:
    return Settings(auth_bypass=True)


@pytest.fixture
async def state(settings: Settings) -> AppState:
    http = httpx.AsyncClient()
    in_app = InAppIntegration(settings)
    registry = IntegrationRegistry()
    registry.register(in_app)
    fake_alerts = FakeAlertService(in_app)
    st = AppState(
        settings=settings,
        http=http,
        llm=FakeLLM(),  # type: ignore[arg-type]
        warehouse=FakeWarehouse(),  # type: ignore[arg-type]
        cache=CacheService(maxsize=16, ttl=60),
        sessions=SessionStore(settings),
        telemetry=TelemetryLogger(settings),
        registry=registry,
        user_auth=UserAuthService(settings, http),
        service_auth=ServiceAuthService(settings),
        in_app=in_app,
        alerts=fake_alerts,  # type: ignore[arg-type]
        alert_scheduler=AlertScheduler(settings, fake_alerts),  # type: ignore[arg-type]
    )
    st.sessions.start()
    st.telemetry.start()
    yield st
    await st.sessions.stop()
    await st.telemetry.stop()
    await http.aclose()


@pytest.fixture
async def client(state: AppState):
    app = create_app()
    app.dependency_overrides[get_state] = lambda: state
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        email="tester@unifiediq.dev", name="Tester", groups=["dev"]
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
