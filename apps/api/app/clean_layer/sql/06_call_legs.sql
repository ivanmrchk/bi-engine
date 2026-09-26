-- The dialed business line ("VPS Number") tells which location a leg
-- belongs to. 'Unknown' caller or connecting numbers become NULL.
INSERT INTO clean.call_legs (
    leg_fingerprint, location_name, started_at, direction, caller_number,
    connecting_number, billed_seconds, leg_type, first_file_id
)
SELECT
    leg.leg_fingerprint,
    line.location_name,
    clean.from_pacific_wall_clock(leg.fields->>'Date/Time'),
    lower(leg.fields->>'Direction'),
    clean.phone_e164(leg.fields->>'Caller ID'),
    clean.phone_e164(leg.fields->>'Connecting #'),
    clean.grasshopper_seconds(leg.fields->>'Duration'),
    leg.fields->>'Type',
    leg.first_file_id
FROM staging.grasshopper_legs AS leg
JOIN reference.locations AS line
    ON line.business_line = clean.phone_e164(leg.fields->>'VPS Number');
