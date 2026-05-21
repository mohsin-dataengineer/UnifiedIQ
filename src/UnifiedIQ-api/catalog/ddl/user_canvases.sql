-- user_canvases: container for pinned views. A draft canvas is mutable; a
-- published canvas is an immutable snapshot produced via POST /api/canvases/{id}/publish.
-- Multi-tenancy by user_email (Principle 7).

CREATE TABLE IF NOT EXISTS user_canvases (
    canvas_id          VARCHAR(64)   NOT NULL,
    user_email         VARCHAR(320)  NOT NULL,
    name               VARCHAR(256)  NOT NULL,
    status             VARCHAR(16)   NOT NULL,   -- draft | published
    source_canvas_id   VARCHAR(64),              -- set when status=published
    created_at         TIMESTAMP     NOT NULL,
    updated_at         TIMESTAMP     NOT NULL,
    PRIMARY KEY (canvas_id)
);
