-- Grasshopper logs legs, not calls. Every inbound leg starts a call: either
-- someone calling in, or ('Mobile Inbound') the owner's cell ringing in to
-- place a call from the Grasshopper app, which makes it an outbound call.
INSERT INTO clean.calls (call_id, location_name, started_at, direction, first_leg_fingerprint)
SELECT
    row_number() OVER (ORDER BY started_at, leg_fingerprint),
    location_name,
    started_at,
    CASE WHEN leg_type = 'Mobile Inbound' THEN 'outbound' ELSE 'inbound' END,
    leg_fingerprint
FROM clean.call_legs
WHERE direction = 'in';

UPDATE clean.call_legs AS leg
SET call_id = call.call_id
FROM clean.calls AS call
WHERE call.first_leg_fingerprint = leg.leg_fingerprint;

-- Each outbound leg belongs to the latest call on the same line that could
-- have produced it. The app dials out within a second or two of the owner's
-- cell ringing in; a forward follows its inbound leg within seconds, or up to
-- a minute or so when the owner doesn't pick up and it rolls on to the AI.
UPDATE clean.call_legs AS leg
SET call_id = (
    SELECT call.call_id
    FROM clean.calls AS call
    WHERE call.location_name = leg.location_name
      AND call.started_at <= leg.started_at
      AND (
          (leg.leg_type LIKE 'Mobile Outbound%'
              AND call.direction = 'outbound'
              AND call.started_at >= leg.started_at - INTERVAL '5 seconds')
          OR
          (leg.leg_type NOT LIKE 'Mobile Outbound%'
              AND call.direction = 'inbound'
              AND call.started_at >= leg.started_at - INTERVAL '2 minutes')
      )
    ORDER BY call.started_at DESC
    LIMIT 1
)
WHERE leg.direction = 'out';

-- What happened on each call, read from its legs.
UPDATE clean.calls AS call
SET outside_number = summary.outside_number,
    outcome        = summary.outcome,
    talk_seconds   = summary.talk_seconds
FROM (
    SELECT
        leg.call_id,
        CASE
            WHEN bool_or(leg.leg_type = 'Mobile Inbound')
                THEN max(leg.connecting_number) FILTER (WHERE leg.leg_type LIKE 'Mobile Outbound%')
            ELSE max(leg.caller_number) FILTER (WHERE leg.direction = 'in')
        END AS outside_number,
        CASE
            WHEN bool_or(leg.leg_type = 'Mobile Outbound Connected') THEN 'connected'
            WHEN bool_or(leg.leg_type = 'Mobile Inbound') THEN 'not_connected'
            WHEN bool_or(leg.leg_type = 'Forwarded call connected' AND ai.phone_e164 IS NOT NULL) THEN 'answered_by_ai'
            WHEN bool_or(leg.leg_type = 'Forwarded call connected') THEN 'answered_by_owner'
            WHEN bool_or(leg.leg_type = 'Voice mail') THEN 'voicemail'
            ELSE 'missed'
        END AS outcome,
        coalesce(
            max(leg.billed_seconds) FILTER (WHERE leg.leg_type IN ('Forwarded call connected', 'Mobile Outbound Connected')),
            0
        ) AS talk_seconds
    FROM clean.call_legs AS leg
    LEFT JOIN reference.internal_phone_numbers AS ai
        ON ai.phone_e164 = leg.connecting_number AND ai.role = 'ai_call_taker'
    WHERE leg.call_id IS NOT NULL
    GROUP BY leg.call_id
) AS summary
WHERE summary.call_id = call.call_id;
