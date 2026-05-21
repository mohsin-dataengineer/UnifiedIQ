-- user_memory: persistent facts/preferences (Tier 4 of the memory strategy).
-- Generic ANSI SQL. Databricks: USING DELTA, STRING for TEXT, TIMESTAMP.
-- Every row carries user_email (Principle 7).

CREATE TABLE IF NOT EXISTS user_memory (
    id            VARCHAR(64)   NOT NULL,
    user_email    VARCHAR(320)  NOT NULL,
    value         TEXT          NOT NULL,
    created_at    TIMESTAMP     NOT NULL,
    updated_at    TIMESTAMP     NOT NULL,
    PRIMARY KEY (id)
);

-- CREATE INDEX idx_user_memory_user ON user_memory (user_email);
