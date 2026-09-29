-- Analytics: business-ready numbers, aggregated from the clean layer.
--
-- Months are Pacific calendar months: a job finished at 9pm on May 31 in
-- Seattle is May revenue, even though it's already June 1 in UTC.

CREATE SCHEMA analytics;

-- Real jobs and their revenue, by the month the work was completed.
CREATE VIEW analytics.service_months AS
SELECT
    date_trunc('month', completed_at AT TIME ZONE 'America/Los_Angeles')::DATE AS month,
    location_name,
    city,
    service,
    count(*) AS jobs,
    sum(total_cents) AS revenue_cents
FROM clean.jobs
WHERE is_real_job
GROUP BY 1, 2, 3, 4;
