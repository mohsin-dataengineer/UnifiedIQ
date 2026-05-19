-- unifiediq_alerts: natural-language monitors. Every row carries user_email
-- (Principle 7). Generic ANSI SQL; on Databricks use USING DELTA, STRING for
-- TEXT, TIMESTAMP for timestamps, DOUBLE for threshold/last_value.

CREATE TABLE IF NOT EXISTS unifiediq_alerts (
    id                VARCHAR(64)   NOT NULL,
    user_email        VARCHAR(320)  NOT NULL,
    title             VARCHAR(512)  NOT NULL,
    natural_language  TEXT          NOT NULL,
    metric_sql        TEXT          NOT NULL,
    comparator        VARCHAR(8)    NOT NULL,   -- lt|lte|gt|gte|eq|neq
    threshold         DOUBLE        NOT NULL,
    channel           VARCHAR(16)   NOT NULL,   -- in_app|slack|email
    recipient         VARCHAR(320),
    cadence_minutes   INTEGER       NOT NULL,
    enabled           BOOLEAN       NOT NULL,
    last_state        VARCHAR(16)   NOT NULL,   -- pending|ok|breached|error
    last_value        DOUBLE,
    last_checked_at   TIMESTAMP,
    created_at        TIMESTAMP     NOT NULL,
    PRIMARY KEY (id)
);

-- CREATE INDEX idx_unifiediq_alerts_user ON unifiediq_alerts (user_email);
