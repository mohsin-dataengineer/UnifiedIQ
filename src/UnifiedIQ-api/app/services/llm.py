"""LLMService - chat, structured outputs, and token streaming.

The `openai` async client is pointed at the Databricks Foundation Model API
(OpenAI-compatible). Structured outputs go through `instructor` so any logic
that branches on model output routes on a validated Pydantic model
(Architectural Principle 3).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Sequence
from typing import Any, TypeVar

import instructor
from instructor.exceptions import InstructorRetryException
from openai import AsyncOpenAI
from pydantic import BaseModel

from app.config import Settings
from app.errors import LLM_INVALID_OUTPUT, LLM_UNAVAILABLE, AppError

logger = logging.getLogger(__name__)

Message = dict[str, str]
TModel = TypeVar("TModel", bound=BaseModel)


class LLMService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )
        # MD_JSON (fenced JSON block) instead of JSON: Databricks serving
        # endpoints reject response_format=json_object unless the messages
        # literally contain "json" and have other quirks; MD_JSON avoids
        # response_format entirely and is broadly compatible.
        self._structured = instructor.from_openai(self._client, mode=instructor.Mode.MD_JSON)

    async def chat(
        self,
        messages: Sequence[Message],
        *,
        model: str | None = None,
        temperature: float = 0,
    ) -> str:
        try:
            completion = await self._client.chat.completions.create(
                model=model or self._settings.llm_default_model,
                messages=list(messages),
                temperature=temperature,
            )
        except Exception as exc:  # noqa: BLE001 - normalized to a stable code
            logger.exception("llm chat failed")
            raise AppError(LLM_UNAVAILABLE, "LLM request failed", status_code=502) from exc
        return completion.choices[0].message.content or ""

    async def chat_structured(
        self,
        messages: Sequence[Message],
        response_model: type[TModel],
        *,
        model: str | None = None,
        temperature: float = 0,
        max_retries: int = 2,
    ) -> tuple[TModel, Any]:
        try:
            result, completion = await self._structured.chat.completions.create_with_completion(
                model=model or self._settings.llm_default_model,
                messages=list(messages),
                response_model=response_model,
                temperature=temperature,
                max_retries=max_retries,
            )
        except InstructorRetryException as exc:
            logger.exception("llm structured output validation failed")
            raise AppError(
                LLM_INVALID_OUTPUT,
                "Model did not return a valid structured response",
                status_code=502,
            ) from exc
        except Exception as exc:  # noqa: BLE001 - normalized to a stable code
            logger.exception("llm structured call failed")
            raise AppError(LLM_UNAVAILABLE, "LLM request failed", status_code=502) from exc
        return result, completion

    async def stream(
        self,
        messages: Sequence[Message],
        *,
        model: str | None = None,
        temperature: float = 0,
    ) -> AsyncIterator[str]:
        try:
            stream = await self._client.chat.completions.create(
                model=model or self._settings.llm_default_model,
                messages=list(messages),
                temperature=temperature,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as exc:  # noqa: BLE001 - normalized to a stable code
            logger.exception("llm stream failed")
            raise AppError(LLM_UNAVAILABLE, "LLM stream failed", status_code=502) from exc
