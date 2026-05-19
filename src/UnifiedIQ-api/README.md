# UnifiedIQ API

FastAPI backend for UnifiedIQ — governed conversational analytics over a
Databricks SQL warehouse, with Databricks Vector Search RAG and Databricks
Foundation Model API for LLM calls.

## Stack

- Python 3.12, FastAPI + Uvicorn
- Pydantic v2 + pydantic-settings
- `openai` client (pointed at Databricks FM API) + `instructor` for structured outputs
- `sqlglot` (dialect `databricks`) for SQL validation
- `cachetools.TTLCache`, `httpx`, async-queue workers

## Layout

```
app/          FastAPI app, config, deps, routers, services, integrations
catalog/ddl/  Warehouse-agnostic CREATE TABLE statements
eval/         Layered evaluation framework (L1-L4) + reports
tests/        pytest (asyncio_mode = auto)
```

## Local dev

```bash
cp .env.example .env          # fill in Databricks + Okta values
pip install ".[dev]"
uvicorn app.main:app --reload --port 5000
```

Or use the repo-root `make dev` (Docker Compose).

## Configuration

All settings are environment-driven via `app/config.py` (`Settings`).
Every variable is documented in `.env.example`. For local development without
an identity provider, set `AUTH_BYPASS=true`.

## Tests & eval

```bash
pytest
python eval/run_eval.py --golden eval/golden_test_set.json --write-report
```
