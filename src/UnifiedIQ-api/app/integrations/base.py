"""Integration framework contract (Part 2.7).

Concrete providers live in sibling modules and register at startup.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.models.domain import AuthContext, HealthStatus


class BaseIntegration(ABC):
    name: str

    @abstractmethod
    async def authenticate(self, user_token: str | None) -> AuthContext: ...

    @abstractmethod
    async def execute(self, action: str, params: dict[str, Any], *, ctx: AuthContext) -> Any: ...

    @abstractmethod
    async def health(self) -> HealthStatus: ...
