-- Clean layer: typed, normalized, deduplicated tables derived from raw.*.
--
-- Conventions, applied by the normalizers:
--   * phone numbers are E.164 ('+14255550142'), or NULL when absent
--   * timestamps are TIMESTAMPTZ (absolute moments), whatever the source's format
--   * money is BIGINT cents, never floating point
--   * empty strings from sources become NULL: "absent" has one spelling
--   * location is inferred from the zip code, since no source records it reliably

CREATE SCHEMA clean;

-- Housecall Pro ------------------------------------------------------------

-- first_seen_at is when the customer first appears in Housecall Pro. Call
-- attribution needs it: a caller only counts as an existing customer if
-- they were already known at the moment of the call.
CREATE TABLE clean.customers (
    customer_id   TEXT PRIMARY KEY,
    first_name    TEXT,
    last_name     TEXT,
    email         TEXT,
    first_seen_at TIMESTAMPTZ NOT NULL
);

-- Every number a customer has ever given, for matching calls and web leads.
CREATE TABLE clean.customer_phone_numbers (
    phone_e164  TEXT NOT NULL,
    customer_id TEXT NOT NULL REFERENCES clean.customers (customer_id),
    PRIMARY KEY (phone_e164, customer_id)
);

-- is_real_job is false for canceled jobs and estimate-only visits, which
-- Housecall Pro also marks "complete".
CREATE TABLE clean.jobs (
    job_id                    TEXT PRIMARY KEY,
    customer_id               TEXT NOT NULL REFERENCES clean.customers (customer_id),
    description               TEXT,
    service                   TEXT,
    work_status               TEXT NOT NULL,
    city                      TEXT,
    zip_code                  TEXT,
    location_name             TEXT REFERENCES reference.locations (location_name),
    lead_source               TEXT,
    created_at                TIMESTAMPTZ NOT NULL,
    scheduled_start           TIMESTAMPTZ,
    completed_at              TIMESTAMPTZ,
    total_cents               BIGINT NOT NULL,
    outstanding_balance_cents BIGINT NOT NULL,
    is_real_job               BOOLEAN NOT NULL
);
CREATE INDEX idx_jobs_customer ON clean.jobs (customer_id);
CREATE INDEX idx_jobs_completed_at ON clean.jobs (completed_at);

CREATE TABLE clean.invoices (
    invoice_id   TEXT PRIMARY KEY,
    job_id       TEXT NOT NULL REFERENCES clean.jobs (job_id),
    status       TEXT NOT NULL,
    amount_cents BIGINT NOT NULL,
    invoice_date TIMESTAMPTZ,
    service_date TIMESTAMPTZ,
    paid_at      TIMESTAMPTZ
);
CREATE INDEX idx_invoices_job ON clean.invoices (job_id);

-- approval_status NULL means the customer never answered.
CREATE TABLE clean.estimates (
    estimate_id        TEXT PRIMARY KEY,
    customer_id        TEXT NOT NULL REFERENCES clean.customers (customer_id),
    service            TEXT,
    city               TEXT,
    zip_code           TEXT,
    location_name      TEXT REFERENCES reference.locations (location_name),
    lead_source        TEXT,
    quoted_total_cents BIGINT NOT NULL,
    approval_status    TEXT CHECK (approval_status IN ('approved', 'declined')),
    created_at         TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_estimates_customer ON clean.estimates (customer_id);

-- Grasshopper ------------------------------------------------------------------

-- One row per call leg, however many weekly exports it appeared in. The
-- fingerprint is a hash of the leg's own fields, since exports carry no id.
CREATE TABLE clean.call_legs (
    leg_fingerprint   TEXT PRIMARY KEY,
    location_name     TEXT NOT NULL REFERENCES reference.locations (location_name),
    started_at        TIMESTAMPTZ NOT NULL,
    direction         TEXT NOT NULL CHECK (direction IN ('in', 'out')),
    caller_number     TEXT,  -- NULL where the export says "Unknown"
    connecting_number TEXT,  -- NULL where the export says "Unknown"
    billed_seconds    INTEGER NOT NULL,
    leg_type          TEXT NOT NULL,
    first_file_id     BIGINT NOT NULL REFERENCES raw.ingested_files (file_id)
);
CREATE INDEX idx_call_legs_started_at ON clean.call_legs (started_at);

-- Website -------------------------------------------------------------------

CREATE TABLE clean.website_submissions (
    submission_id              INTEGER PRIMARY KEY,
    form_id                    INTEGER NOT NULL,
    submitted_at               TIMESTAMPTZ NOT NULL,
    name                       TEXT,
    phone_e164                 TEXT,
    email                      TEXT,
    zip_code                   TEXT,
    location_name              TEXT REFERENCES reference.locations (location_name),
    message                    TEXT,
    utm_source                 TEXT,
    utm_medium                 TEXT,
    utm_campaign               TEXT,
    gclid                      TEXT,
    fbclid                     TEXT,
    referrer                   TEXT,
    entry_page                 TEXT,
    submit_page                TEXT,
    is_spam                    BOOLEAN NOT NULL,
    duplicate_of_submission_id INTEGER REFERENCES clean.website_submissions (submission_id)
);
CREATE INDEX idx_website_submissions_phone ON clean.website_submissions (phone_e164);

-- Search Console -------------------------------------------------------------

-- The day's true totals. They include anonymized queries, so they are
-- larger than the sum of that day's rows in search_query_pages.
CREATE TABLE clean.search_daily_totals (
    day         DATE PRIMARY KEY,
    clicks      INTEGER NOT NULL,
    impressions INTEGER NOT NULL,
    position    DOUBLE PRECISION NOT NULL
);

CREATE TABLE clean.search_query_pages (
    day         DATE NOT NULL,
    query       TEXT NOT NULL,
    page_path   TEXT NOT NULL,
    clicks      INTEGER NOT NULL,
    impressions INTEGER NOT NULL,
    position    DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (day, query, page_path)
);
