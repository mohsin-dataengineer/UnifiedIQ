-- chatbot_history: one row per interaction turn (question + assistant result).
-- Generic ANSI SQL. Databricks: replace TIMESTAMP with TIMESTAMP, JSON columns
-- with STRING (store JSON text) or VARIANT, and prefer a Delta table:
--   CREATE TABLE main.analytics.chatbot_history (...) USING DELTA;
-- Logical multi-tenancy: every row carries user_email (Principle 7).

CREATE TABLE IF NOT EXISTS chatbot_history (
    interaction_id   VARCHAR(64)   NOT NULL,
    session_id       VARCHAR(64)   NOT NULL,
    user_email       VARCHAR(320)  NOT NULL,
    question         TEXT          NOT NULL,
    intent           VARCHAR(16)   NOT NULL,   -- data | chart | reject | clarify
    generated_sql    TEXT,
    chart_config     TEXT,                      -- JSON text
    answer           TEXT,
    assumptions      TEXT,                      -- JSON array text
    citations        TEXT,                      -- JSON array text
    latency_ms       INTEGER,
    tokens_in        INTEGER,
    tokens_out       INTEGER,
    created_at       TIMESTAMP     NOT NULL,
    PRIMARY KEY (interaction_id)
);

-- Databricks does not enforce PK/indexes; for OLTP-style stores add:
-- CREATE INDEX idx_chatbot_history_session ON chatbot_history (session_id);
-- CREATE INDEX idx_chatbot_history_user    ON chatbot_history (user_email);
