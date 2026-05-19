"""SSE serialization with the fixed event vocabulary (Part 2.5).

Only these event names are valid: thinking, sql, chart, data, citation,
done, error. A stream must always terminate with `done` or `error`.
"""

from __future__ import annotations

import json
from typing import Any, Literal

SSEEvent = Literal["thinking", "sql", "chart", "data", "citation", "done", "error"]


def sse(event: SSEEvent, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"
