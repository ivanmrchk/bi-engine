-- Views for comparing cities over time.

-- Every job, by the Pacific month it was booked. Grouping by booking month
-- (not completion month) keeps a job with the demand that produced it, so
-- a month's conversion means "of the jobs booked then, how many became real work".
CREATE VIEW analytics.booked_jobs AS
SELECT
    date_trunc('month', created_at AT TIME ZONE 'America/Los_Angeles')::DATE AS booked_month,
    location_name,
    city,
    is_real_job,
    total_cents
FROM clean.jobs
WHERE city IS NOT NULL;

-- Search impressions and clicks for each city's landing pages, such as
-- '/panel-upgrade-bellevue-wa/'. A page's city is the slug before '-wa/'.
CREATE VIEW analytics.city_search_months AS
SELECT
    date_trunc('month', search.day)::DATE AS month,
    area.city,
    sum(search.impressions) AS impressions,
    sum(search.clicks) AS clicks
FROM clean.search_query_pages AS search
JOIN (
    SELECT DISTINCT city, lower(regexp_replace(city, '[^A-Za-z0-9]+', '-', 'g')) AS slug
    FROM reference.service_area_zip_codes
) AS area ON search.page_path LIKE '%-' || area.slug || '-wa/'
GROUP BY 1, 2;
