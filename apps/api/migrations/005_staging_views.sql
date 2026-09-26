-- Staging: the raw files unpacked into one row per source record.
--
-- Sources get re-pulled (a Housecall Pro job appears again once it's
-- completed; Search Console revises recent days), so every view keeps only
-- the record's latest version: the one from the most recently stored file.
-- Views hold no data of their own; they always reflect what's in raw.*.

CREATE SCHEMA staging;

CREATE VIEW staging.housecall_pro_jobs AS
SELECT DISTINCT ON (job->>'id')
    job->>'id' AS job_id,
    job AS record
FROM raw.ingested_files AS file
JOIN raw.json_documents AS document USING (file_id)
CROSS JOIN LATERAL jsonb_array_elements(document.body->'jobs') AS job
WHERE file.feed = 'housecall_pro_jobs'
ORDER BY job->>'id', file.file_id DESC;

CREATE VIEW staging.housecall_pro_invoices AS
SELECT DISTINCT ON (invoice->>'id')
    invoice->>'id' AS invoice_id,
    invoice AS record
FROM raw.ingested_files AS file
JOIN raw.json_documents AS document USING (file_id)
CROSS JOIN LATERAL jsonb_array_elements(document.body->'invoices') AS invoice
WHERE file.feed = 'housecall_pro_invoices'
ORDER BY invoice->>'id', file.file_id DESC;

CREATE VIEW staging.housecall_pro_estimates AS
SELECT DISTINCT ON (estimate->>'id')
    estimate->>'id' AS estimate_id,
    estimate AS record
FROM raw.ingested_files AS file
JOIN raw.json_documents AS document USING (file_id)
CROSS JOIN LATERAL jsonb_array_elements(document.body->'estimates') AS estimate
WHERE file.feed = 'housecall_pro_estimates'
ORDER BY estimate->>'id', file.file_id DESC;

-- The customer block, retyped on every job and estimate, with the moment
-- of the record it came from.
CREATE VIEW staging.housecall_pro_customer_records AS
SELECT record->'customer' AS customer, (record->>'created_at')::TIMESTAMPTZ AS recorded_at
FROM staging.housecall_pro_jobs
UNION ALL
SELECT record->'customer' AS customer, (record->>'created_at')::TIMESTAMPTZ AS recorded_at
FROM staging.housecall_pro_estimates;

-- Weekly call exports overlap, and the export has no call id, so a leg is
-- identified by a hash of all its fields. JSONB stores keys in a canonical
-- order, so identical rows from different files hash identically.
CREATE VIEW staging.grasshopper_legs AS
SELECT DISTINCT ON (md5(csv_row.fields::TEXT))
    md5(csv_row.fields::TEXT) AS leg_fingerprint,
    csv_row.fields,
    csv_row.file_id AS first_file_id
FROM raw.ingested_files AS file
JOIN raw.csv_rows AS csv_row USING (file_id)
WHERE file.feed = 'grasshopper_calls'
ORDER BY md5(csv_row.fields::TEXT), csv_row.file_id;

CREATE VIEW staging.website_leads AS
SELECT DISTINCT ON ((lead->>'id')::INTEGER)
    (lead->>'id')::INTEGER AS submission_id,
    lead AS record
FROM raw.ingested_files AS file
JOIN raw.json_documents AS document USING (file_id)
CROSS JOIN LATERAL jsonb_array_elements(document.body->'leads') AS lead
WHERE file.feed = 'website_leads'
ORDER BY (lead->>'id')::INTEGER, file.file_id DESC;

-- One Search Console response per day and request type. The query/page
-- response doesn't repeat the date in its rows, so the day comes from the
-- file name (YYYY-MM-DD.json), which the fetcher sets when it stores it.
CREATE VIEW staging.search_console_totals AS
SELECT DISTINCT ON (day)
    day,
    document.body->'rows'->0 AS totals
FROM raw.ingested_files AS file
JOIN raw.json_documents AS document USING (file_id)
CROSS JOIN LATERAL (SELECT left(file.file_name, 10)::DATE AS day) AS file_day
WHERE file.feed = 'search_console_totals'
  AND jsonb_array_length(document.body->'rows') > 0
ORDER BY day, file.file_id DESC;

CREATE VIEW staging.search_console_query_pages AS
WITH latest_file_per_day AS (
    SELECT DISTINCT ON (left(file.file_name, 10)) file.file_id, left(file.file_name, 10)::DATE AS day
    FROM raw.ingested_files AS file
    WHERE file.feed = 'search_console_query_pages'
    ORDER BY left(file.file_name, 10), file.file_id DESC
)
SELECT latest.day, query_row AS row
FROM latest_file_per_day AS latest
JOIN raw.json_documents AS document USING (file_id)
CROSS JOIN LATERAL jsonb_array_elements(document.body->'rows') AS query_row;
