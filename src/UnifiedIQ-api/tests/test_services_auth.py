import httpx
import pytest
from app.config import Settings
from app.errors import AppError
from app.services.auth import UserAuthService


async def test_bypass_returns_dev_user():
    settings = Settings(auth_bypass=True)
    async with httpx.AsyncClient() as http:
        svc = UserAuthService(settings, http)
        user = await svc.authenticate(None)
        assert user.email == "dev@localhost"


async def test_bypass_prefers_header_identity():
    settings = Settings(auth_bypass=True)
    async with httpx.AsyncClient() as http:
        svc = UserAuthService(settings, http)
        user = await svc.authenticate(None, header_email="real@corp.com", header_name="Real")
        assert user.email == "real@corp.com"


async def test_missing_bearer_is_unauthenticated():
    settings = Settings(auth_bypass=False)
    async with httpx.AsyncClient() as http:
        svc = UserAuthService(settings, http)
        with pytest.raises(AppError) as exc:
            await svc.authenticate(None)
        assert exc.value.code == "UNAUTHENTICATED"


async def test_databricks_mode_trusts_forwarded_identity():
    settings = Settings(auth_mode="databricks", auth_bypass=False)
    async with httpx.AsyncClient() as http:
        svc = UserAuthService(settings, http)
        user = await svc.authenticate(
            None,
            forwarded_email="alice@corp.com",
            forwarded_user="alice",
        )
        assert user.email == "alice@corp.com"
        assert user.name == "alice"


async def test_databricks_mode_requires_forwarded_email():
    settings = Settings(auth_mode="databricks", auth_bypass=False)
    async with httpx.AsyncClient() as http:
        svc = UserAuthService(settings, http)
        with pytest.raises(AppError) as exc:
            await svc.authenticate(None)
        assert exc.value.code == "UNAUTHENTICATED"
