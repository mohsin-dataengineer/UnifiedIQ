"""Two-layer auth (Part 2.8).

UserAuthService validates the incoming OIDC bearer (Okta) and yields the
end user. ServiceAuthService holds the machine principal used for durable
writes. AUTH_BYPASS short-circuits user validation for local dev only.
"""

from __future__ import annotations

import logging

import httpx
import jwt

from app.config import Settings
from app.errors import FORBIDDEN, UNAUTHENTICATED, AppError
from app.models.domain import AuthContext, CurrentUser

logger = logging.getLogger(__name__)

_BYPASS_USER = CurrentUser(email="dev@localhost", name="Local Dev", groups=["dev"])


class UserAuthService:
    def __init__(self, settings: Settings, http: httpx.AsyncClient) -> None:
        self._settings = settings
        self._http = http
        self._jwk_client: jwt.PyJWKClient | None = None
        self._jwks_uri: str | None = None

    async def _get_jwk_client(self) -> jwt.PyJWKClient:
        if self._jwk_client is None:
            well_known = (
                f"{self._settings.oidc_issuer.rstrip('/')}/.well-known/openid-configuration"
            )
            resp = await self._http.get(well_known)
            resp.raise_for_status()
            self._jwks_uri = resp.json()["jwks_uri"]
            self._jwk_client = jwt.PyJWKClient(
                self._jwks_uri,
                cache_keys=True,
                lifespan=self._settings.oidc_jwks_ttl_seconds,
            )
        return self._jwk_client

    async def authenticate(
        self,
        bearer: str | None,
        *,
        header_email: str | None = None,
        header_name: str | None = None,
        forwarded_email: str | None = None,
        forwarded_user: str | None = None,
    ) -> CurrentUser:
        if self._settings.auth_bypass:
            if header_email:
                return CurrentUser(
                    email=header_email,
                    name=header_name,
                    groups=_BYPASS_USER.groups,
                )
            return _BYPASS_USER

        if self._settings.auth_mode == "databricks":
            # Databricks Apps terminate SSO at the platform edge and set
            # these headers; the client cannot forge them.
            if not forwarded_email:
                raise AppError(
                    UNAUTHENTICATED,
                    "Missing Databricks forwarded identity",
                    status_code=401,
                )
            return CurrentUser(email=forwarded_email, name=forwarded_user, groups=[])

        if not bearer:
            raise AppError(UNAUTHENTICATED, "Missing bearer token", status_code=401)

        try:
            jwk_client = await self._get_jwk_client()
            signing_key = jwk_client.get_signing_key_from_jwt(bearer)
            claims = jwt.decode(
                bearer,
                signing_key.key,
                algorithms=["RS256"],
                audience=self._settings.oidc_audience,
                issuer=self._settings.oidc_issuer,
            )
        except Exception as exc:  # noqa: BLE001 - normalized to a stable code
            logger.warning("token validation failed: %s", exc)
            raise AppError(UNAUTHENTICATED, "Invalid bearer token", status_code=401) from exc

        email = claims.get("email") or claims.get("sub")
        if not email:
            raise AppError(UNAUTHENTICATED, "Token has no subject", status_code=401)
        groups = list(claims.get("groups", []))

        allowed = self._settings.allowed_groups
        if allowed and not set(allowed) & set(groups):
            raise AppError(FORBIDDEN, "User not in an allowed group", status_code=403)

        return CurrentUser(email=email, name=claims.get("name"), groups=groups)


class ServiceAuthService:
    """Machine principal for durable, non-user-attributed writes."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def context(self) -> AuthContext:
        return AuthContext(
            principal=self._settings.service_principal_id,
            token=self._settings.service_principal_token,
            metadata={"layer": "service"},
        )
