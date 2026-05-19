-- eval_results: one row per evaluated golden case per run (L1-L4 outcomes).
-- Generic ANSI SQL. Databricks: USING DELTA, STRING for TEXT/JSON.
-- Carries user_email of the runner for multi-tenant attribution (Principle 7).

CREATE TABLE IF NOT EXISTS eval_results (
    run_id          VARCHAR(96)   NOT NULL,   -- <git-sha>-<timestamp>
    git_sha         VARCHAR(40)   NOT NULL,
    case_id         VARCHAR(32)   NOT NULL,
    tier            VARCHAR(16)   NOT NULL,   -- core | edge | regression
    user_email      VARCHAR(320)  NOT NULL,
    l1_syntax_pass  BOOLEAN,
    l2_structure_pass BOOLEAN,
    l3_parity_pass  BOOLEAN,
    l4_judge_score  DECIMAL(4,3),
    failure_tags    TEXT,                      -- JSON array text
    detail          TEXT,                      -- JSON text (per-case diff)
    created_at      TIMESTAMP     NOT NULL,
    PRIMARY KEY (run_id, case_id)
);

-- CREATE INDEX idx_eval_results_run ON eval_results (run_id);
