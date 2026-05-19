-- user_views: saved/pinned views and dashboard layouts per user.
-- Generic ANSI SQL. Databricks: USING DELTA, STRING for TEXT/JSON, VARIANT
-- acceptable for layout. Every row carries user_email (Principle 7).

CREATE TABLE IF NOT EXISTS user_views (
    view_id       VARCHAR(64)   NOT NULL,
    user_email    VARCHAR(320)  NOT NULL,
    name          VARCHAR(256)  NOT NULL,
    kind          VARCHAR(32)   NOT NULL,   -- chart | table | dashboard
    spec          TEXT          NOT NULL,   -- JSON text (chart/dashboard spec)
    is_shared     BOOLEAN       NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMP     NOT NULL,
    updated_at    TIMESTAMP     NOT NULL,
    PRIMARY KEY (view_id)
);

-- CREATE INDEX idx_user_views_user ON user_views (user_email);
