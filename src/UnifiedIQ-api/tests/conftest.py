from __future__ import annotations

from typing import Any

import httpx
import pytest
from app.config import Settings
from app.deps import AppState, get_current_user, get_state
from app.integrations.in_app import InAppIntegration
from app.main import create_app
from app.models.domain import (
    Alert,
    Canvas,
    CurrentUser,
    UserMemory,
    UserView,
    ViewSpec,
)
from app.models.responses import (
    AlertSpec,
    AlternativeSQLResponse,
    JudgeScore,
    SQLGenerationResponse,
)
from app.services.alerts import AlertScheduler
from app.services.auth import ServiceAuthService, UserAuthService
from app.services.cache import CacheService
from app.services.integration_registry import IntegrationRegistry
from app.services.session_store import SessionStore
from app.services.telemetry import TelemetryLogger
from app.services.verifier import VerifierService


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
        self.alt_sql = AlternativeSQLResponse(
            alternative_sql=(
                "WITH s AS (SELECT region, revenue FROM sales) "
                "SELECT region, SUM(revenue) AS r FROM s GROUP BY region"
            ),
            approach="CTE rewrite with explicit aggregation",
        )
        self.judge = JudgeScore(
            verdict="agree",
            confidence=0.9,
            rationale="snapshots match within tolerance",
        )

    async def chat_structured(
        self, messages: Any, response_model: Any, **kwargs: Any
    ) -> tuple[Any, Any]:
        if response_model is AlertSpec:
            return self.alert, {"usage": {}}
        if response_model is AlternativeSQLResponse:
            return self.alt_sql, {"usage": {}}
        if response_model is JudgeScore:
            return self.judge, {"usage": {}}
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


class FakeCanvasService:
    def __init__(self) -> None:
        self._canvases: dict[str, Canvas] = {}

    async def ensure_table(self) -> None:
        return None

    async def create(self, user_email, name) -> Canvas:  # noqa: ANN001
        import uuid

        c = Canvas(id=uuid.uuid4().hex, user_email=user_email, name=name)
        self._canvases[c.id] = c
        return c

    async def list(self, user_email) -> list[Canvas]:  # noqa: ANN001
        return sorted(
            [c for c in self._canvases.values() if c.user_email == user_email],
            key=lambda c: c.created_at,
            reverse=True,
        )

    async def get(self, user_email, canvas_id) -> Canvas | None:  # noqa: ANN001
        c = self._canvases.get(canvas_id)
        return c if c and c.user_email == user_email else None

    async def rename(self, user_email, canvas_id, name) -> Canvas | None:  # noqa: ANN001
        from app.errors import FORBIDDEN, AppError

        c = await self.get(user_email, canvas_id)
        if c is None:
            return None
        if c.status == "published":
            raise AppError(FORBIDDEN, "Immutable.", status_code=403)
        c.name = name
        return c

    async def delete(self, user_email, canvas_id) -> None:  # noqa: ANN001
        from app.errors import FORBIDDEN, AppError

        c = await self.get(user_email, canvas_id)
        if c is None:
            return
        if c.status == "published":
            raise AppError(FORBIDDEN, "Immutable.", status_code=403)
        self._canvases.pop(canvas_id, None)

    async def create_published(self, user_email, source) -> Canvas:  # noqa: ANN001
        import uuid

        from app.errors import FORBIDDEN, AppError

        if source.status == "published":
            raise AppError(FORBIDDEN, "Already published.", status_code=403)
        published = Canvas(
            id=uuid.uuid4().hex,
            user_email=user_email,
            name=source.name,
            status="published",
            source_canvas_id=source.id,
        )
        self._canvases[published.id] = published
        return published

    async def ensure_default(self, user_email) -> Canvas:  # noqa: ANN001
        for c in await self.list(user_email):
            if c.status == "draft":
                return c
        return await self.create(user_email, "My canvas")


class FakeViewsService:
    def __init__(self, canvases: FakeCanvasService | None = None) -> None:
        self._views: dict[str, UserView] = {}
        self._canvases = canvases

    def set_canvases(self, canvases: FakeCanvasService) -> None:
        self._canvases = canvases

    async def ensure_table(self) -> None:
        return None

    async def backfill_canvas_ids(self) -> None:
        return None

    async def _assert_writable(self, user_email, canvas_id):  # noqa: ANN001
        from app.errors import FORBIDDEN, AppError

        if not canvas_id or self._canvases is None:
            return
        canvas = await self._canvases.get(user_email, canvas_id)
        if canvas is not None and canvas.status == "published":
            raise AppError(FORBIDDEN, "Immutable.", status_code=403)

    async def create(
        self,
        user_email,  # noqa: ANN001
        name,  # noqa: ANN001
        spec: ViewSpec,
        *,
        kind="chart",  # noqa: ANN001
    ) -> UserView:
        import uuid

        canvas_id = spec.canvas_id
        if not canvas_id and self._canvases is not None:
            default = await self._canvases.ensure_default(user_email)
            canvas_id = default.id
            spec = spec.model_copy(update={"canvas_id": canvas_id})
        await self._assert_writable(user_email, canvas_id)
        v = UserView(
            id=uuid.uuid4().hex,
            user_email=user_email,
            name=name,
            kind=kind,
            spec=spec,
        )
        self._views[v.id] = v
        return v

    async def list(
        self,
        user_email,  # noqa: ANN001
        *,
        canvas_id=None,  # noqa: ANN001
    ) -> list[UserView]:
        items = [v for v in self._views.values() if v.user_email == user_email]
        if canvas_id is not None:
            items = [v for v in items if v.spec.canvas_id == canvas_id]
        return items

    async def update(
        self,
        user_email,  # noqa: ANN001
        view_id,  # noqa: ANN001
        *,
        name=None,  # noqa: ANN001
        spec_patch=None,  # noqa: ANN001
    ) -> UserView | None:
        v = self._views.get(view_id)
        if v is None or v.user_email != user_email:
            return None
        await self._assert_writable(user_email, v.spec.canvas_id)
        if name is not None:
            v.name = name
        if spec_patch:
            merged = v.spec.model_dump()
            for k, val in spec_patch.items():
                if k == "canvas_id":
                    continue
                merged[k] = val
            v.spec = ViewSpec.model_validate(merged)
        return v

    async def get(self, user_email, view_id) -> UserView | None:  # noqa: ANN001
        v = self._views.get(view_id)
        return v if v and v.user_email == user_email else None

    async def delete(self, user_email, view_id) -> None:  # noqa: ANN001
        v = self._views.get(view_id)
        if v and v.user_email == user_email:
            await self._assert_writable(user_email, v.spec.canvas_id)
            self._views.pop(view_id, None)

    async def copy_for_publish(
        self,
        user_email,  # noqa: ANN001
        target_canvas_id,  # noqa: ANN001
        source_views,  # noqa: ANN001
    ):
        import uuid

        copies = []
        for v in source_views:
            new_spec = v.spec.model_copy(update={"canvas_id": target_canvas_id})
            new_view = UserView(
                id=uuid.uuid4().hex,
                user_email=user_email,
                name=v.name,
                kind=v.kind,
                spec=new_spec,
            )
            self._views[new_view.id] = new_view
            copies.append(new_view)
        return copies

    async def delete_in_canvas(self, user_email, canvas_id) -> None:  # noqa: ANN001
        for vid in [
            v.id
            for v in list(self._views.values())
            if v.user_email == user_email and v.spec.canvas_id == canvas_id
        ]:
            self._views.pop(vid, None)

    async def run(self, user_email, view_id):  # noqa: ANN001, ANN201
        v = await self.get(user_email, view_id)
        if v is None:
            return None
        # Static fake rows so the dashboard renders deterministically in tests.
        return v, [{"k": "a", "v": 1}, {"k": "b", "v": 2}]


class FakeSchemaService:
    """Returns a deterministic schema block so chat tests are isolated."""

    async def context_block(self, question: str) -> str:  # noqa: ANN001
        return "## Available tables\nworkspace.demo.sales(region string, revenue double)"


class FakeUserMemoryService:
    def __init__(self) -> None:
        self._items: dict[str, UserMemory] = {}

    async def ensure_table(self) -> None:
        return None

    async def list(self, user_email) -> list[UserMemory]:  # noqa: ANN001
        return [m for m in self._items.values() if m.user_email == user_email]

    async def create(self, user_email, value) -> UserMemory:  # noqa: ANN001
        import uuid

        m = UserMemory(id=uuid.uuid4().hex, user_email=user_email, value=value)
        self._items[m.id] = m
        return m

    async def delete(self, user_email, memory_id) -> None:  # noqa: ANN001
        m = self._items.get(memory_id)
        if m and m.user_email == user_email:
            self._items.pop(memory_id, None)

    async def context_block(self, user_email) -> str:  # noqa: ANN001
        items = await self.list(user_email)
        if not items:
            return ""
        return "## User context (remember about this user)\n" + "\n".join(
            f"- {m.value}" for m in items
        )


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
    fake_llm = FakeLLM()
    fake_wh = FakeWarehouse()
    fake_canvases = FakeCanvasService()
    fake_views = FakeViewsService(canvases=fake_canvases)
    st = AppState(
        settings=settings,
        http=http,
        llm=fake_llm,  # type: ignore[arg-type]
        warehouse=fake_wh,  # type: ignore[arg-type]
        cache=CacheService(maxsize=16, ttl=60),
        sessions=SessionStore(settings),
        telemetry=TelemetryLogger(settings),
        registry=registry,
        user_auth=UserAuthService(settings, http),
        service_auth=ServiceAuthService(settings),
        in_app=in_app,
        alerts=fake_alerts,  # type: ignore[arg-type]
        alert_scheduler=AlertScheduler(settings, fake_alerts),  # type: ignore[arg-type]
        views=fake_views,  # type: ignore[arg-type]
        canvases=fake_canvases,  # type: ignore[arg-type]
        verifier=VerifierService(fake_llm, fake_wh),  # type: ignore[arg-type]
        schema=FakeSchemaService(),  # type: ignore[arg-type]
        user_memory=FakeUserMemoryService(),  # type: ignore[arg-type]
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
