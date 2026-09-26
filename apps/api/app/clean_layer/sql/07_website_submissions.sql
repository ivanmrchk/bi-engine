-- Spam is flagged, not deleted, by two signals: a sales pitch in the
-- message, or no zip code from a phone number outside the local area codes.
INSERT INTO clean.website_submissions (
    submission_id, form_id, submitted_at, name, phone_e164, email, zip_code, location_name,
    message, utm_source, utm_medium, utm_campaign, gclid, fbclid, referrer,
    entry_page, submit_page, is_spam
)
SELECT
    submission.submission_id,
    (lead.record->>'cf7_form_id')::INTEGER,
    clean.from_pacific_wall_clock(lead.record->>'created_at'),
    clean.blank_to_null(lead.record->>'name'),
    submission.phone_e164,
    lower(clean.blank_to_null(lead.record->>'email')),
    submission.zip_code,
    zip.location_name,
    submission.message,
    clean.blank_to_null(lead.record->'acquisition_params'->>'utm_source'),
    clean.blank_to_null(lead.record->'acquisition_params'->>'utm_medium'),
    clean.blank_to_null(lead.record->'acquisition_params'->>'utm_campaign'),
    clean.blank_to_null(lead.record->'acquisition_params'->>'gclid'),
    clean.blank_to_null(lead.record->'acquisition_params'->>'fbclid'),
    clean.blank_to_null(lead.record->'acquisition_params'->>'ref'),
    clean.blank_to_null(lead.record->>'entry_page'),
    clean.blank_to_null(lead.record->>'submit_page'),
    coalesce(
        submission.message ~* '(seo|#1 on google|funding|credit check|redesign|pay per lead|leads in your area|serving the .* area)',
        false  -- a blank message contains no pitch
    ) OR (submission.zip_code IS NULL AND local_code.area_code IS NULL)
FROM staging.website_leads AS lead
CROSS JOIN LATERAL (
    SELECT
        lead.submission_id,
        clean.phone_e164(lead.record->>'phone') AS phone_e164,
        clean.blank_to_null(lead.record->>'zipcode') AS zip_code,
        clean.blank_to_null(lead.record->>'message') AS message
) AS submission
LEFT JOIN reference.service_area_zip_codes AS zip ON zip.zip_code = submission.zip_code
LEFT JOIN reference.local_area_codes AS local_code
    ON local_code.area_code = substring(submission.phone_e164 FROM 3 FOR 3);

-- A double click sends the same form twice within seconds. Later copies
-- point at the first one instead of counting as leads of their own.
UPDATE clean.website_submissions AS later
SET duplicate_of_submission_id = (
    SELECT min(earlier.submission_id)
    FROM clean.website_submissions AS earlier
    WHERE earlier.submission_id < later.submission_id
      AND earlier.phone_e164 = later.phone_e164
      AND earlier.message IS NOT DISTINCT FROM later.message
      AND earlier.submitted_at >= later.submitted_at - INTERVAL '10 minutes'
);
