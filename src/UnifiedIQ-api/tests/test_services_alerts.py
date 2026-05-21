from typing import Any

from app.config import Settings
from app.integrations.in_app import InAppIntegration
from app.models.domain import Alert
from app.services.alerts import AlertService, breached
from app.services.integration_registry import IntegrationRegistry


def test_breached_all_comparators():
    assert breached(5, "lt", 10)
    assert not breached(15, "lt", 10)
    assert breached(10, "lte", 10)
    assert breached(11, "gt", 10)
    assert breached(10, "gte", 10)
    assert breached(10, "eq", 10)
    assert breached(9, "neq", 10)


class MetricWarehouse:
    """Returns a numeric metric for SELECT; swallows writes."""

    def __init__(self, value: float) -> None:
        self.value = value

    async def execute(self, sql: str, *, params: Any = None) -> list[dict]:
        if sql.strip().upper().startswith("SELECT"):
            return [{"v": self.value}]
        return []

    async def execute_to_arrow(self, sql: str):  # noqa: ANN201
        raise NotImplementedError

    async def health(self) -> bool:
        return True


def _alert(**kw: Any) -> Alert:
    base: dict[str, Any] = {
        "id": "a1",
        "user_email": "u@x.com",
        "title": "Low signups",
        "natural_language": "signups < 1000",
        "metric_sql": "SELECT COUNT(*) AS v FROM signups",
        "comparator": "lt",
        "threshold": 1000.0,
        "channel": "in_app",
        "cadence_minutes": 60,
    }
    base.update(kw)
    return Alert(**base)


async def test_evaluate_fires_once_on_transition():
    settings = Settings()
    registry = IntegrationRegistry()
    in_app = InAppIntegration(settings)
    registry.register(in_app)
    svc = AlertService(settings, MetricWarehouse(42), registry)

    alert = _alert()
    await svc.evaluate_one(alert)
    assert alert.last_state == "breached"
    assert len(in_app.recent("u@x.com")) == 1

    # Already breached -> no duplicate notification.
    await svc.evaluate_one(alert)
    assert len(in_app.recent("u@x.com")) == 1


async def test_delete_clears_in_app_notifications():
    settings = Settings()
    registry = IntegrationRegistry()
    in_app = InAppIntegration(settings)
    registry.register(in_app)
    svc = AlertService(settings, MetricWarehouse(42), registry)

    alert = _alert()
    await svc.evaluate_one(alert)
    assert len(in_app.recent("u@x.com")) == 1

    await svc.delete("u@x.com", alert.id)
    assert in_app.recent("u@x.com") == []


async def test_evaluate_ok_when_not_breached():
    settings = Settings()
    registry = IntegrationRegistry()
    in_app = InAppIntegration(settings)
    registry.register(in_app)
    svc = AlertService(settings, MetricWarehouse(5000), registry)

    alert = _alert()
    await svc.evaluate_one(alert)
    assert alert.last_state == "ok"
    assert in_app.recent("u@x.com") == []
