INSERT INTO clean.search_daily_totals (day, clicks, impressions, position)
SELECT
    day,
    (totals->>'clicks')::INTEGER,
    (totals->>'impressions')::INTEGER,
    (totals->>'position')::DOUBLE PRECISION
FROM staging.search_console_totals;

-- Rows name the full page URL; keep just the path so it lines up with the
-- landing pages recorded on website form submissions.
INSERT INTO clean.search_query_pages (day, query, page_path, clicks, impressions, position)
SELECT
    day,
    row->'keys'->>0,
    regexp_replace(row->'keys'->>1, '^https?://[^/]+', ''),
    (row->>'clicks')::INTEGER,
    (row->>'impressions')::INTEGER,
    (row->>'position')::DOUBLE PRECISION
FROM staging.search_console_query_pages;
