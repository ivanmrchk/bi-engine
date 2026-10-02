-- Technicians' notes, dated by when the work happened and tagged with the
-- job's city, service, and location.
INSERT INTO clean.notes (note_id, kind, written_on, location_name, city, service, job_id, body)
SELECT
    note->>'id',
    'job_note',
    (coalesce(job.completed_at, job.scheduled_start, job.created_at) AT TIME ZONE 'America/Los_Angeles')::DATE,
    job.location_name,
    job.city,
    job.service,
    job.job_id,
    note->>'content'
FROM staging.housecall_pro_jobs AS staged
CROSS JOIN LATERAL jsonb_array_elements(staged.record->'notes') AS note
JOIN clean.jobs AS job ON job.job_id = staged.job_id
WHERE clean.blank_to_null(note->>'content') IS NOT NULL;

-- The owner's monthly notes ('2026-01.md'), one row per paragraph. The
-- '# January 2026' heading is left out. A paragraph that names a city we
-- serve is tagged with it.
INSERT INTO clean.notes (note_id, kind, written_on, location_name, city, body)
SELECT
    'owner-' || left(file.file_name, 7) || '-' || paragraph.position,
    'owner_note',
    (left(file.file_name, 7) || '-01')::DATE,
    city_mentioned.location_name,
    city_mentioned.city,
    btrim(paragraph.text)
FROM raw.ingested_files AS file
JOIN raw.text_documents AS document USING (file_id)
CROSS JOIN LATERAL regexp_split_to_table(document.body, '\n\s*\n') WITH ORDINALITY AS paragraph (text, position)
LEFT JOIN LATERAL (
    SELECT DISTINCT area.city, area.location_name
    FROM reference.service_area_zip_codes AS area
    WHERE paragraph.text ILIKE '%' || area.city || '%'
    ORDER BY area.city
    LIMIT 1
) AS city_mentioned ON true
WHERE file.feed = 'owner_notes'
  AND file.file_name ~ '^\d{4}-\d{2}\.md$'
  AND clean.blank_to_null(paragraph.text) IS NOT NULL
  AND btrim(paragraph.text) NOT LIKE '#%';
