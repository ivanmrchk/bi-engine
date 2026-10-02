-- Leads: every first contact, by web form or by phone, in one table,
-- with the marketing channel it came from and the job it became.

-- What the office's "lead source" dropdown in Housecall Pro means as a
-- channel. "Google" can't distinguish search from the Business Profile,
-- and "Website" can't distinguish organic search from ChatGPT.
CREATE TABLE reference.office_lead_sources (
    lead_source TEXT PRIMARY KEY,
    channel     TEXT NOT NULL
);

INSERT INTO reference.office_lead_sources (lead_source, channel) VALUES
    ('Google', 'google_search_or_profile'),
    ('Google Ads', 'google_ads'),
    ('Referral', 'referral'),
    ('Website', 'website_unspecified');

-- channel_evidence records how sure the channel is: tracking tags on the
-- web visit are strongest, then the referring site, then the office's
-- dropdown choice. Phone calls have no tracking at all.
CREATE TABLE clean.leads (
    lead_id               TEXT PRIMARY KEY,  -- 'web-123' or 'call-456'
    contact_method        TEXT NOT NULL CHECK (contact_method IN ('web_form', 'phone_call')),
    contacted_at          TIMESTAMPTZ NOT NULL,
    location_name         TEXT REFERENCES reference.locations (location_name),
    customer_id           TEXT REFERENCES clean.customers (customer_id),
    is_returning_customer BOOLEAN NOT NULL,
    channel               TEXT NOT NULL CHECK (channel IN (
                              'google_ads', 'google_business_profile', 'google_search_or_profile',
                              'chatgpt', 'referral', 'website_unspecified', 'unknown'
                          )),
    channel_evidence      TEXT NOT NULL CHECK (channel_evidence IN (
                              'tracking_tags', 'referrer', 'office_lead_source', 'none'
                          )),
    job_id                TEXT REFERENCES clean.jobs (job_id)  -- the job it became, if any
);
CREATE INDEX idx_leads_contacted_at ON clean.leads (contacted_at);
