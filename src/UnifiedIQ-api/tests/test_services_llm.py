import pytest
from app.config import Settings
from app.errors import AppError
from app.models.responses import SQLGenerationResponse
from app.services.llm import LLMService


async def test_structured_failure_maps_to_stable_code(monkeypatch):
    svc = LLMService(Settings())

    async def boom(*args, **kwargs):
        raise RuntimeError("connection refused")

    # Exercises the except-path that previously leaked an AttributeError
    # (instructor.exceptions vs instructor.core.exceptions) as INTERNAL.
    monkeypatch.setattr(
        svc._structured.chat.completions,
        "create_with_completion",
        boom,
    )

    with pytest.raises(AppError) as exc:
        await svc.chat_structured(
            [{"role": "user", "content": "hi"}],
            response_model=SQLGenerationResponse,
        )
    assert exc.value.code == "LLM_UNAVAILABLE"
    assert exc.value.status_code == 502
