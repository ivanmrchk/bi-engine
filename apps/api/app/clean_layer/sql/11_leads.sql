-- Web form leads: real submissions only, so no spam and no double clicks.
-- The customer is matched by phone, or by email when the phone doesn't match.
INSERT INTO clean.leads (
    lead_id, contact_method, contacted_at, location_name, customer_id,
    is_returning_customer, channel, channel_evidence
)
SELECT
    'web-' || submission.submission_id,
    'web_form',
    submission.submitted_at,
    submission.location_name,
    matched.customer_id,
    coalesce(matched.first_seen_at < submission.submitted_at - INTERVAL '1 hour', false),
    CASE
        WHEN submission.utm_medium = 'cpc' OR submission.gclid IS NOT NULL THEN 'google_ads'
        WHEN submission.utm_campaign = 'gbp-listing' THEN 'google_business_profile'
        WHEN submission.utm_source ILIKE '%chatgpt%' OR submission.referrer ILIKE '%chatgpt.com%' THEN 'chatgpt'
        WHEN submission.fbclid IS NOT NULL
          OR submission.referrer ILIKE '%facebook.com%'
          OR submission.referrer ILIKE '%nextdoor.com%' THEN 'referral'
        -- Untagged Google traffic: organic search and the Business Profile look identical.
        WHEN submission.referrer ILIKE '%google.%' THEN 'google_search_or_profile'
        ELSE 'unknown'
    END,
    CASE
        WHEN submission.utm_source IS NOT NULL OR submission.gclid IS NOT NULL OR submission.fbclid IS NOT NULL
            THEN 'tracking_tags'
        WHEN submission.referrer IS NOT NULL THEN 'referrer'
        ELSE 'none'
    END
FROM clean.website_submissions AS submission
LEFT JOIN LATERAL (
    SELECT customer.customer_id, customer.first_seen_at
    FROM clean.customers AS customer
    WHERE customer.email = submission.email
       OR customer.customer_id IN (
              SELECT phone.customer_id
              FROM clean.customer_phone_numbers AS phone
              WHERE phone.phone_e164 = submission.phone_e164
          )
    ORDER BY customer.first_seen_at
    LIMIT 1
) AS matched ON true
WHERE NOT submission.is_spam
  AND submission.duplicate_of_submission_id IS NULL;

-- Phone leads: inbound calls the attribution step classified as leads.
-- A phone call carries no channel; the office's dropdown may fill it in below.
INSERT INTO clean.leads (
    lead_id, contact_method, contacted_at, location_name, customer_id,
    is_returning_customer, channel, channel_evidence
)
SELECT
    'call-' || call.call_id,
    'phone_call',
    call.started_at,
    call.location_name,
    call.customer_id,
    call.classification = 'returning_customer_lead',
    'unknown',
    'none'
FROM clean.calls AS call
WHERE call.direction = 'inbound'
  AND call.classification IN ('new_customer_lead', 'returning_customer_lead', 'unconverted_caller');

-- The job each lead became: the customer's first job booked from just
-- before the contact until two weeks after it.
UPDATE clean.leads AS lead
SET job_id = (
    SELECT job.job_id
    FROM clean.jobs AS job
    WHERE job.customer_id = lead.customer_id
      AND job.created_at BETWEEN lead.contacted_at - INTERVAL '1 hour' AND lead.contacted_at + INTERVAL '14 days'
    ORDER BY job.created_at
    LIMIT 1
)
WHERE lead.customer_id IS NOT NULL;

-- Leads still without a channel take the office's lead source from the job.
UPDATE clean.leads AS lead
SET channel = office_source.channel,
    channel_evidence = 'office_lead_source'
FROM clean.jobs AS job
JOIN reference.office_lead_sources AS office_source ON office_source.lead_source = job.lead_source
WHERE job.job_id = lead.job_id
  AND lead.channel = 'unknown';
