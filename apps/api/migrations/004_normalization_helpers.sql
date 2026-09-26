-- Helpers the clean-layer rebuild uses to turn each source's quirks into
-- one canonical form. Each function handles exactly one kind of mess.

-- '(425) 555-0142', '425.555.0142', '14255550142', '+1 425 555 0142' -> '+14255550142'.
-- Anything that isn't a North American number ('Unknown', '') becomes NULL.
CREATE FUNCTION clean.phone_e164(raw_phone TEXT) RETURNS TEXT
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN length(digits) = 10 THEN '+1' || digits
        WHEN length(digits) = 11 AND left(digits, 1) = '1' THEN '+' || digits
    END
    FROM (SELECT regexp_replace(coalesce(raw_phone, ''), '\D', '', 'g') AS digits) AS only_digits
$$;

-- '' and '   ' mean "absent" just as NULL does; give absence one spelling.
CREATE FUNCTION clean.blank_to_null(value TEXT) RETURNS TEXT
LANGUAGE sql IMMUTABLE AS $$
    SELECT NULLIF(btrim(value), '')
$$;

-- Grasshopper's Excel-proofed duration: '="2:12"' -> 132 seconds.
CREATE FUNCTION clean.grasshopper_seconds(raw_duration TEXT) RETURNS INTEGER
LANGUAGE sql IMMUTABLE AS $$
    SELECT split_part(minutes_and_seconds, ':', 1)::INTEGER * 60
         + split_part(minutes_and_seconds, ':', 2)::INTEGER
    FROM (SELECT btrim(raw_duration, '="') AS minutes_and_seconds) AS unwrapped
$$;

-- A local wall-clock time with no zone, as Grasshopper ('9/25/2026 4:54:11 PM')
-- and WordPress ('2026-06-29 16:05:34') write them, read as Pacific time.
-- The date style is pinned so month/day order never depends on server settings.
CREATE FUNCTION clean.from_pacific_wall_clock(wall_clock TEXT) RETURNS TIMESTAMPTZ
LANGUAGE sql STABLE
SET datestyle = 'ISO, MDY'
AS $$
    SELECT wall_clock::TIMESTAMP AT TIME ZONE 'America/Los_Angeles'
$$;

-- How the office describes each kind of job. The longest phrase found in a
-- description wins, so 'outlets dead' (a power problem) beats 'outlet'
-- (an installation), and 'tripping' beats 'breaker'.
CREATE TABLE reference.service_keywords (
    keyword TEXT PRIMARY KEY,  -- lowercase
    service TEXT NOT NULL
);

INSERT INTO reference.service_keywords (keyword, service) VALUES
    ('no power', 'No-Power Troubleshooting'),
    ('lost power', 'No-Power Troubleshooting'),
    ('outlets dead', 'No-Power Troubleshooting'),
    ('outlet', 'Outlet & Switch Installation'),
    ('switch', 'Outlet & Switch Installation'),
    ('gfci', 'Outlet & Switch Installation'),
    ('light fixture', 'Light Fixture Installation'),
    ('recessed', 'Light Fixture Installation'),
    ('chandelier', 'Light Fixture Installation'),
    ('flickering', 'Diagnostic Visit'),
    ('tripping', 'Diagnostic Visit'),
    ('burning smell', 'Diagnostic Visit'),
    ('ev charger', 'EV Charger Installation'),
    ('tesla', 'EV Charger Installation'),
    ('level 2 charger', 'EV Charger Installation'),
    ('panel', 'Panel Upgrade'),
    ('service upgrade', 'Panel Upgrade'),
    ('heated floor', 'Heated Floor Wiring'),
    ('floor heat', 'Heated Floor Wiring'),
    ('office', 'Commercial Electrical Work'),
    ('tenant', 'Commercial Electrical Work'),
    ('restaurant', 'Commercial Electrical Work'),
    ('generator', 'Generator Installation'),
    ('hot tub', 'Hot Tub Wiring'),
    ('spa ', 'Hot Tub Wiring'),
    ('breaker', 'Circuit Breaker Replacement'),
    ('afci', 'Circuit Breaker Replacement');

CREATE FUNCTION clean.service_from_description(description TEXT) RETURNS TEXT
LANGUAGE sql STABLE AS $$
    SELECT service
    FROM reference.service_keywords
    WHERE position(keyword IN lower(description)) > 0
    ORDER BY length(keyword) DESC
    LIMIT 1
$$;

-- Area codes of the markets the company serves. A form submitted from a
-- far-away number with no zip code is a strong spam signal.
CREATE TABLE reference.local_area_codes (
    area_code TEXT PRIMARY KEY
);

INSERT INTO reference.local_area_codes (area_code) VALUES ('206'), ('253'), ('360'), ('425');
