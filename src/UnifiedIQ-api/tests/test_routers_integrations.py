from typing import Any

from app.integrations.base import BaseIntegration
from app.integrations.email_smtp import EmailIntegration
from app.integrations.slack import SlackIntegration
from app.models.domain import AuthContext, HealthStatus


class FakeIntegration(BaseIntegration):
    name = "fake"

    async def authenticate(self, user_token: str | None) -> AuthContext:
        return AuthContext(principal="fake")

    async def execute(self, action: str, params: dict[str, Any], *, ctx: AuthContext) -> Any:
        return {"echo": action, "params": params}

    async def health(self) -> HealthStatus:
        return HealthStatus(name=self.name, healthy=True)


async def test_list_integrations(client, state):
    state.registry.register(FakeIntegration())
    resp = await client.get("/api/integrations")
    assert resp.status_code == 200
    names = {h["name"] for h in resp.json()}
    assert "fake" in names


async def test_execute_integration(client, state):
    state.registry.register(FakeIntegration())
    resp = await client.post(
        "/api/integrations/fake/execute",
        json={"action": "ping", "params": {"x": 1}},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["integration"] == "fake"
    assert body["result"] == {"echo": "ping", "params": {"x": 1}}


async def test_unknown_integration_returns_stable_code(client):
    resp = await client.post(
        "/api/integrations/nope/execute",
        json={"action": "x", "params": {}},
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "INTEGRATION_NOT_FOUND"


async def test_unconfigured_providers_report_not_configured(client, state):
    state.registry.register(SlackIntegration(state.settings, state.http))
    state.registry.register(EmailIntegration(state.settings))
    resp = await client.get("/api/integrations")
    health = {h["name"]: h for h in resp.json()}
    assert health["slack"]["healthy"] is False
    assert health["slack"]["detail"] == "not configured"
    assert health["email"]["healthy"] is False
    assert health["email"]["detail"] == "not configured"
