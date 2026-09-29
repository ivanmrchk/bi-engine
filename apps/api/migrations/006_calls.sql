-- Calls: Grasshopper's legs reassembled into the conversations they belong
-- to, with who was on the other end and why they called.

-- Attribution needs to know which internal number is which: a call forwarded
-- to the AI call taker was answered by the AI, not the owner.
ALTER TABLE reference.internal_phone_numbers
    ADD COLUMN role TEXT CHECK (role IN ('owner_cell', 'ai_call_taker'));
UPDATE reference.internal_phone_numbers SET role = 'owner_cell' WHERE phone_e164 = '+13605550100';
UPDATE reference.internal_phone_numbers SET role = 'ai_call_taker' WHERE phone_e164 = '+15415550100';
ALTER TABLE reference.internal_phone_numbers ALTER COLUMN role SET NOT NULL;

-- outcome, talk_seconds, and classification are filled in by later steps
-- of the rebuild, after every call has been assembled.
CREATE TABLE clean.calls (
    call_id               INTEGER PRIMARY KEY,
    location_name         TEXT NOT NULL REFERENCES reference.locations (location_name),
    started_at            TIMESTAMPTZ NOT NULL,
    direction             TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    first_leg_fingerprint TEXT NOT NULL UNIQUE REFERENCES clean.call_legs (leg_fingerprint),
    outside_number        TEXT,
    outcome               TEXT CHECK (outcome IN (
                              'answered_by_owner', 'answered_by_ai', 'voicemail', 'missed',
                              'connected', 'not_connected'
                          )),
    talk_seconds          INTEGER,
    customer_id           TEXT REFERENCES clean.customers (customer_id),
    classification        TEXT CHECK (classification IN (
                              'new_customer_lead',        -- first contact from someone who became a customer
                              'returning_customer_lead',  -- a past customer asking for new work
                              'unconverted_caller',       -- a local number that never became a customer
                              'job_related',              -- a customer about work already booked
                              'existing_customer_other',  -- a customer, with nothing open and nothing new
                              'missed_call_callback',     -- the owner returning a missed lead call
                              'web_form_follow_up',       -- the owner calling back a web form
                              'visit_day',                -- the owner calling ahead of a visit
                              'business_contact',         -- suppliers and the like, recognized by behavior
                              'spam',                     -- a number from outside the local area codes
                              'internal',                 -- the company's own numbers
                              'unknown'                   -- no outside number to go on
                          ))
);
CREATE INDEX idx_calls_location_started_at ON clean.calls (location_name, started_at);
CREATE INDEX idx_calls_outside_number ON clean.calls (outside_number);

ALTER TABLE clean.call_legs ADD COLUMN call_id INTEGER REFERENCES clean.calls (call_id);
