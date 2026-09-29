-- Why each call happened, worked out from timing alone: when the number
-- became a customer, what work they had open, and what was created after.

-- The customer behind each call's outside number, if any. A number shared
-- by two customers goes to the one who has been a customer longest.
UPDATE clean.calls AS call
SET customer_id = (
    SELECT phone.customer_id
    FROM clean.customer_phone_numbers AS phone
    JOIN clean.customers AS customer USING (customer_id)
    WHERE phone.phone_e164 = call.outside_number
    ORDER BY customer.first_seen_at
    LIMIT 1
);

-- Every call first gets the rules for someone calling in. The first rule
-- that fits wins, so the order below is the order of precedence.
WITH number_history AS (
    SELECT outside_number, count(*) AS call_count, max(started_at) - min(started_at) AS active_span
    FROM clean.calls
    WHERE outside_number IS NOT NULL
    GROUP BY outside_number
)
UPDATE clean.calls AS call
SET classification = classified.classification
FROM (
    SELECT
        call.call_id,
        CASE
            WHEN call.outside_number IS NULL THEN 'unknown'
            WHEN internal.phone_e164 IS NOT NULL THEN 'internal'
            WHEN local_code.area_code IS NULL THEN 'spam'
            -- Never a customer. Suppliers and inspectors keep calling for
            -- months; a lead who didn't book calls once or twice.
            WHEN customer.customer_id IS NULL THEN
                CASE WHEN history.call_count >= 5 AND history.active_span >= INTERVAL '60 days'
                     THEN 'business_contact'
                     ELSE 'unconverted_caller'
                END
            -- The office creates a customer during or just after their first
            -- call, so a customer who appears after the call was a new lead.
            WHEN customer.first_seen_at >= call.started_at - INTERVAL '1 hour' THEN
                CASE WHEN customer.first_seen_at <= call.started_at + INTERVAL '14 days'
                     THEN 'new_customer_lead'
                     ELSE 'unconverted_caller'
                END
            -- A known customer: a new job soon after the call means they were
            -- asking for it, even if another job was still open. A new
            -- estimate only counts when nothing was open; while a job is
            -- open, an estimate is usually the written quote for that job.
            WHEN new_work.job_was_created
                OR (new_work.estimate_was_created AND NOT open_job.is_open)
                THEN 'returning_customer_lead'
            WHEN open_job.is_open THEN 'job_related'
            ELSE 'existing_customer_other'
        END AS classification
    FROM clean.calls AS call
    LEFT JOIN reference.internal_phone_numbers AS internal
        ON internal.phone_e164 = call.outside_number
    LEFT JOIN reference.local_area_codes AS local_code
        ON local_code.area_code = substring(call.outside_number FROM 3 FOR 3)
    LEFT JOIN clean.customers AS customer ON customer.customer_id = call.customer_id
    LEFT JOIN number_history AS history ON history.outside_number = call.outside_number
    CROSS JOIN LATERAL (
        SELECT
            EXISTS (
                SELECT 1 FROM clean.jobs AS job
                WHERE job.customer_id = call.customer_id
                  AND job.created_at BETWEEN call.started_at - INTERVAL '1 hour' AND call.started_at + INTERVAL '14 days'
            ) AS job_was_created,
            EXISTS (
                SELECT 1 FROM clean.estimates AS estimate
                WHERE estimate.customer_id = call.customer_id
                  AND estimate.created_at BETWEEN call.started_at - INTERVAL '1 hour' AND call.started_at + INTERVAL '14 days'
            ) AS estimate_was_created
    ) AS new_work
    -- A job is open from booking until the day after its visit (if canceled)
    -- or two weeks after it's done, while scheduling and invoice questions
    -- come in. The extra day covers calls later on the day the window ends.
    CROSS JOIN LATERAL (
        SELECT EXISTS (
            SELECT 1 FROM clean.jobs AS job
            WHERE job.customer_id = call.customer_id
              AND job.created_at <= call.started_at
              AND call.started_at <= CASE
                      WHEN job.completed_at IS NOT NULL THEN job.completed_at + INTERVAL '15 days'
                      ELSE job.scheduled_start + INTERVAL '1 day'
                  END
        ) AS is_open
    ) AS open_job
) AS classified
WHERE classified.call_id = call.call_id;

-- A call the owner places is explained by what just happened: a missed call
-- from that number, a web form submitted from it, or a visit about to start.
UPDATE clean.calls AS call
SET classification = explained.classification
FROM (
    SELECT
        call.call_id,
        CASE
            WHEN returned_call.classification IN ('new_customer_lead', 'returning_customer_lead', 'unconverted_caller')
                THEN 'missed_call_callback'
            -- Returning a supplier's or a customer's call is still their business.
            WHEN returned_call.classification IS NOT NULL THEN returned_call.classification
            WHEN web_form.was_submitted THEN 'web_form_follow_up'
            WHEN visit.is_about_to_start THEN 'visit_day'
            ELSE call.classification
        END AS classification
    FROM clean.calls AS call
    LEFT JOIN LATERAL (
        SELECT inbound.classification
        FROM clean.calls AS inbound
        WHERE inbound.outside_number = call.outside_number
          AND inbound.direction = 'inbound'
          AND inbound.outcome IN ('missed', 'voicemail')
          AND inbound.started_at BETWEEN call.started_at - INTERVAL '4 hours' AND call.started_at
        ORDER BY inbound.started_at DESC
        LIMIT 1
    ) AS returned_call ON true
    CROSS JOIN LATERAL (
        SELECT EXISTS (
            SELECT 1 FROM clean.website_submissions AS submission
            WHERE submission.phone_e164 = call.outside_number
              AND NOT submission.is_spam
              AND submission.duplicate_of_submission_id IS NULL
              AND submission.submitted_at BETWEEN call.started_at - INTERVAL '24 hours' AND call.started_at
        ) AS was_submitted
    ) AS web_form
    CROSS JOIN LATERAL (
        SELECT EXISTS (
            SELECT 1 FROM clean.jobs AS job
            WHERE job.customer_id = call.customer_id
              AND job.scheduled_start BETWEEN call.started_at AND call.started_at + INTERVAL '3 hours'
        ) AS is_about_to_start
    ) AS visit
    WHERE call.direction = 'outbound'
      AND call.classification NOT IN ('internal', 'spam', 'unknown')
) AS explained
WHERE explained.call_id = call.call_id;
