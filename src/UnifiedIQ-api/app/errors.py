"""Stable error codes and the application exception type.

Every handled failure raises AppError with a stable `code` string so clients
(and the streaming `error` SSE event) can branch on it without parsing prose.
"""

from __future__ import annotations

from fastapi import HTTPException

# Stable, client-facing error codes. Do not rename without a contract bump.
LLM_UNAVAILABLE = "LLM_UNAVAILABLE"
LLM_INVALID_OUTPUT = "LLM_INVALID_OUTPUT"
WAREHOUSE_TIMEOUT = "WAREHOUSE_TIMEOUT"
WAREHOUSE_ERROR = "WAREHOUSE_ERROR"
SQL_INVALID = "SQL_INVALID"
UNAUTHENTICATED = "UNAUTHENTICATED"
FORBIDDEN = "FORBIDDEN"
INTEGRATION_NOT_FOUND = "INTEGRATION_NOT_FOUND"
INTEGRATION_ERROR = "INTEGRATION_ERROR"
BAD_REQUEST = "BAD_REQUEST"
INTERNAL = "INTERNAL"


class AppError(HTTPException):
    """HTTPException carrying a stable error code in its detail payload."""

    def __init__(self, code: str, message: str, *, status_code: int = 400) -> None:
        super().__init__(status_code=status_code, detail={"code": code, "message": message})
        self.code = code
        self.message = message
