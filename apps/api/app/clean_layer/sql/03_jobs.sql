-- Housecall Pro marks canceled jobs and $99 estimate visits "complete" too.
-- A job is real only if it wasn't canceled and billed at least $150 (the
-- owner's rule for "we were actually hired").
--
-- The city comes from the zip code when it's in the service area, since the
-- typed city is unreliable ('BELLEVUE', 'bellevue', missing).
INSERT INTO clean.jobs (
    job_id, customer_id, description, service, work_status, city, zip_code, location_name,
    lead_source, created_at, scheduled_start, completed_at, total_cents,
    outstanding_balance_cents, is_real_job
)
SELECT
    job.job_id,
    job.record->'customer'->>'id',
    clean.blank_to_null(job.record->>'description'),
    clean.service_from_description(job.record->>'description'),
    job.record->>'work_status',
    coalesce(zip.city, initcap(clean.blank_to_null(job.record->'address'->>'city'))),
    clean.blank_to_null(job.record->'address'->>'zip'),
    zip.location_name,
    clean.blank_to_null(job.record->>'lead_source'),
    (job.record->>'created_at')::TIMESTAMPTZ,
    (job.record->'schedule'->>'scheduled_start')::TIMESTAMPTZ,
    (job.record->'work_timestamps'->>'completed_at')::TIMESTAMPTZ,
    (job.record->>'total_amount')::BIGINT,
    (job.record->>'outstanding_balance')::BIGINT,
    job.record->>'work_status' NOT IN ('user canceled', 'pro canceled')
        AND (job.record->>'total_amount')::BIGINT >= 15000
FROM staging.housecall_pro_jobs AS job
LEFT JOIN reference.service_area_zip_codes AS zip
    ON zip.zip_code = job.record->'address'->>'zip';
