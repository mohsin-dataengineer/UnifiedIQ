-- chatbot_sessions: one row per conversation session.
-- Generic ANSI SQL. Databricks: use USING DELTA, STRING for TEXT,
-- TIMESTAMP for timestamps. Every row carries user_email (Principle 7).

CREATE TABLE IF NOT EXISTS chatbot_sessions (
    session_id    VARCHAR(64)   NOT NULL,
    user_email    VARCHAR(320)  NOT NULL,
    title         VARCHAR(512),
    turn_count    INTEGER       NOT NULL DEFAULT 0,
    created_at    TIMESTAMP     NOT NULL,
    updated_at    TIMESTAMP     NOT NULL,
    PRIMARY KEY (session_id)
);

-- CREATE INDEX idx_chatbot_sessions_user ON chatbot_sessions (user_email);
