-- Notes: what people wrote down, for the RAG layer to search.

-- The owner's monthly notes arrive as Markdown files, a new feed of plain text.
ALTER TABLE raw.ingested_files DROP CONSTRAINT ingested_files_feed_check;
ALTER TABLE raw.ingested_files ADD CONSTRAINT ingested_files_feed_check CHECK (feed IN (
    'housecall_pro_jobs',
    'housecall_pro_invoices',
    'housecall_pro_estimates',
    'grasshopper_calls',
    'website_leads',
    'search_console_totals',
    'search_console_query_pages',
    'owner_notes'
));

CREATE TABLE raw.text_documents (
    file_id BIGINT PRIMARY KEY REFERENCES raw.ingested_files (file_id),
    body    TEXT   NOT NULL
);

-- One row per note: a technician's note on a job, or one paragraph of an
-- owner's monthly note (each paragraph is about one thing, so it's the
-- right size to retrieve on its own). City, service, and location are
-- there for filtering searches, and are NULL when a note doesn't say.
CREATE TABLE clean.notes (
    note_id       TEXT PRIMARY KEY,  -- 'note_job_00012_1' or 'owner-2026-01-3'
    kind          TEXT NOT NULL CHECK (kind IN ('job_note', 'owner_note')),
    written_on    DATE NOT NULL,
    location_name TEXT REFERENCES reference.locations (location_name),
    city          TEXT,
    service       TEXT,
    job_id        TEXT REFERENCES clean.jobs (job_id),
    body          TEXT NOT NULL
);
CREATE INDEX idx_notes_written_on ON clean.notes (written_on);
