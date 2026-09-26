-- Raw layer: every file exactly as it arrived.
--
-- Nothing here is ever updated or deleted, so every clean table can be
-- dropped and rebuilt from these rows at any time. A file's SHA-256 hash
-- makes loading idempotent: the same file uploaded twice is stored once.

CREATE SCHEMA raw;

-- A feed is one stream of same-shaped files from one source.
CREATE TABLE raw.ingested_files (
    file_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    feed           TEXT        NOT NULL CHECK (feed IN (
                       'housecall_pro_jobs',
                       'housecall_pro_invoices',
                       'housecall_pro_estimates',
                       'grasshopper_calls',
                       'website_leads',
                       'search_console_totals',
                       'search_console_query_pages'
                   )),
    file_name      TEXT        NOT NULL,
    content_sha256 TEXT        NOT NULL,
    ingested_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (feed, content_sha256)
);

-- API responses (one page or one day per file), stored whole.
CREATE TABLE raw.json_documents (
    file_id BIGINT PRIMARY KEY REFERENCES raw.ingested_files (file_id),
    body    JSONB  NOT NULL
);

-- CSV exports, one row per data line, keyed by the file's own header.
-- Values stay exactly as written: '="2:12"', 'Unknown', '9/25/2026 4:54:11 PM'.
CREATE TABLE raw.csv_rows (
    file_id     BIGINT  NOT NULL REFERENCES raw.ingested_files (file_id),
    line_number INTEGER NOT NULL,
    fields      JSONB   NOT NULL,
    PRIMARY KEY (file_id, line_number)
);
