from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    app_name: str = "UnifiedIQ"
    app_env: str = "local"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000"
    git_sha: str = "dev"

    # --- LLM (Databricks Foundation Model API, OpenAI-compatible) ---
    llm_base_url: str = "https://example.cloud.databricks.com/serving-endpoints"
    llm_api_key: str = "dapi-replace-me"
    llm_default_model: str = "databricks-claude-sonnet-4"
    llm_embedding_model: str = "databricks-bge-large-en"
    llm_timeout_seconds: float = 60.0
    llm_max_retries: int = 2

    # --- Warehouse (Databricks SQL) ---
    warehouse_server_hostname: str = "example.cloud.databricks.com"
    warehouse_http_path: str = "/sql/1.0/warehouses/replace-me"
    warehouse_access_token: str = "dapi-replace-me"
    warehouse_catalog: str = "main"
    warehouse_schema: str = "analytics"
    warehouse_query_timeout_seconds: float = 30.0

    # --- Vector store (Databricks Vector Search) ---
    vector_search_endpoint: str = "unifiediq-vs-endpoint"
    vector_search_index: str = "main.analytics.kb_docs_index"
    vector_search_top_k: int = 5

    # --- User auth (Okta OIDC) ---
    oidc_issuer: str = "https://example.okta.com/oauth2/default"
    oidc_audience: str = "api://unifiediq"
    oidc_jwks_ttl_seconds: int = 3600
    oidc_allowed_groups: str = ""
    auth_bypass: bool = False
    # oidc (validate Okta bearer) | databricks (trust X-Forwarded-* set by
    # Databricks Apps SSO) | (auth_bypass overrides both for local dev)
    auth_mode: str = "oidc"

    # --- Service auth (machine principal for durable writes) ---
    service_principal_id: str = "unifiediq-svc"
    service_principal_token: str = "replace-me"

    # --- Cache ---
    cache_ttl_seconds: int = 300
    cache_max_size: int = 1024

    # --- Telemetry & session persistence (async queue workers) ---
    worker_flush_max_items: int = 50
    worker_flush_interval_seconds: float = 5.0

    # --- Optional Postgres (app-side store) ---
    database_url: str = ""

    # --- Alerts (natural-language monitors) ---
    alerts_enabled: bool = True
    # Empty -> derived as <catalog>.<schema>.unifiediq_alerts
    alerts_table: str = ""
    # Default matches the minimum alert cadence; scheduler also short-circuits
    # the warehouse SELECT when no alerts are active.
    alerts_poll_interval_seconds: float = 300.0
    alerts_in_app_max: int = 100

    # --- Memory (Tiers 1 & 4) ---
    # Comma-separated <catalog>.<schema> values used by Tier 1 schema grounding.
    schema_sources: str = "workspace.default,samples.nyctaxi"
    schema_ttl_seconds: int = 3600
    schema_max_tables_injected: int = 30
    # Empty -> <catalog>.<schema>.user_memory (Tier 4).
    user_memory_table: str = ""

    # --- Integrations: Slack ---
    slack_bot_token: str = ""
    slack_default_channel: str = "#general"
    slack_api_base: str = "https://slack.com/api"

    # --- Integrations: Email (SMTP) ---
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "unifiediq@example.com"
    smtp_use_tls: bool = True
    smtp_timeout_seconds: float = 10.0

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_groups(self) -> list[str]:
        return [g.strip() for g in self.oidc_allowed_groups.split(",") if g.strip()]

    @property
    def alerts_table_name(self) -> str:
        if self.alerts_table:
            return self.alerts_table
        return f"{self.warehouse_catalog}.{self.warehouse_schema}.unifiediq_alerts"

    @property
    def schema_source_list(self) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        for raw in self.schema_sources.split(","):
            cleaned = raw.strip()
            if not cleaned or "." not in cleaned:
                continue
            catalog, _, schema = cleaned.partition(".")
            if catalog and schema:
                out.append((catalog, schema))
        return out

    @property
    def user_memory_table_name(self) -> str:
        if self.user_memory_table:
            return self.user_memory_table
        return f"{self.warehouse_catalog}.{self.warehouse_schema}.user_memory"


@lru_cache
def get_settings() -> Settings:
    return Settings()
