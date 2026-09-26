-- An estimate's service and total come from its (single) option.
-- approval_status stays NULL while the customer hasn't answered.
INSERT INTO clean.estimates (
    estimate_id, customer_id, service, city, zip_code, location_name, lead_source,
    quoted_total_cents, approval_status, created_at
)
SELECT
    estimate.estimate_id,
    estimate.record->'customer'->>'id',
    clean.service_from_description(estimate.record->'options'->0->>'name'),
    coalesce(zip.city, initcap(clean.blank_to_null(estimate.record->'address'->>'city'))),
    clean.blank_to_null(estimate.record->'address'->>'zip'),
    zip.location_name,
    clean.blank_to_null(estimate.record->>'lead_source'),
    (estimate.record->'options'->0->>'total_amount')::BIGINT,
    estimate.record->'options'->0->>'approval_status',
    (estimate.record->>'created_at')::TIMESTAMPTZ
FROM staging.housecall_pro_estimates AS estimate
LEFT JOIN reference.service_area_zip_codes AS zip
    ON zip.zip_code = estimate.record->'address'->>'zip';
