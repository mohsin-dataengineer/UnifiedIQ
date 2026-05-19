"""IntegrationRegistry - name -> BaseIntegration, populated at startup."""

from __future__ import annotations

from app.errors import INTEGRATION_NOT_FOUND, AppError
from app.integrations.base import BaseIntegration


class IntegrationRegistry:
    def __init__(self) -> None:
        self._integrations: dict[str, BaseIntegration] = {}

    def register(self, integration: BaseIntegration) -> None:
        self._integrations[integration.name] = integration

    def get(self, name: str) -> BaseIntegration:
        integration = self._integrations.get(name)
        if integration is None:
            raise AppError(
                INTEGRATION_NOT_FOUND,
                f"Unknown integration: {name}",
                status_code=404,
            )
        return integration

    def names(self) -> list[str]:
        return sorted(self._integrations)
