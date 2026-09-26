-- Reference data: facts about the business the pipeline needs but no
-- source file contains. The owner knows these; the data doesn't say them.
-- Edit these rows to point the pipeline at a different business.

CREATE SCHEMA reference;

-- Each location has its own Grasshopper line and extension.
CREATE TABLE reference.locations (
    location_name         TEXT PRIMARY KEY,
    business_line         TEXT NOT NULL UNIQUE,  -- E.164
    grasshopper_extension TEXT NOT NULL UNIQUE
);

-- Housecall Pro doesn't record a job's location, so it is inferred
-- from the job's zip code.
CREATE TABLE reference.service_area_zip_codes (
    zip_code      TEXT PRIMARY KEY,
    city          TEXT NOT NULL,
    location_name TEXT NOT NULL REFERENCES reference.locations (location_name)
);

-- Numbers that appear in call logs but are never customers: the owner's
-- cell (outbound app calls log an inbound leg from it) and the AI call taker.
CREATE TABLE reference.internal_phone_numbers (
    phone_e164  TEXT PRIMARY KEY,
    description TEXT NOT NULL
);

INSERT INTO reference.locations (location_name, business_line, grasshopper_extension) VALUES
    ('Eastside',    '+14255550100', '0 - Default Extension'),
    ('South Sound', '+12535550100', '2 - New Extension');

INSERT INTO reference.internal_phone_numbers (phone_e164, description) VALUES
    ('+13605550100', 'Owner''s cell (Grasshopper app)'),
    ('+15415550100', 'Housecall Pro AI call taker');

INSERT INTO reference.service_area_zip_codes (zip_code, city, location_name) VALUES
    ('98027', 'Issaquah', 'Eastside'),      ('98029', 'Issaquah', 'Eastside'),
    ('98074', 'Sammamish', 'Eastside'),     ('98075', 'Sammamish', 'Eastside'),
    ('98004', 'Bellevue', 'Eastside'),      ('98005', 'Bellevue', 'Eastside'),
    ('98006', 'Bellevue', 'Eastside'),      ('98007', 'Bellevue', 'Eastside'),
    ('98008', 'Bellevue', 'Eastside'),
    ('98055', 'Renton', 'Eastside'),        ('98056', 'Renton', 'Eastside'),
    ('98058', 'Renton', 'Eastside'),        ('98059', 'Renton', 'Eastside'),
    ('98103', 'Seattle', 'Eastside'),       ('98105', 'Seattle', 'Eastside'),
    ('98107', 'Seattle', 'Eastside'),       ('98115', 'Seattle', 'Eastside'),
    ('98117', 'Seattle', 'Eastside'),       ('98118', 'Seattle', 'Eastside'),
    ('98052', 'Redmond', 'Eastside'),       ('98053', 'Redmond', 'Eastside'),
    ('98033', 'Kirkland', 'Eastside'),      ('98034', 'Kirkland', 'Eastside'),
    ('98065', 'Snoqualmie', 'Eastside'),
    ('98045', 'North Bend', 'Eastside'),
    ('98040', 'Mercer Island', 'Eastside'),
    ('98038', 'Maple Valley', 'Eastside'),
    ('98030', 'Kent', 'South Sound'),       ('98031', 'Kent', 'South Sound'),
    ('98032', 'Kent', 'South Sound'),
    ('98001', 'Auburn', 'South Sound'),     ('98002', 'Auburn', 'South Sound'),
    ('98092', 'Auburn', 'South Sound'),
    ('98003', 'Federal Way', 'South Sound'),('98023', 'Federal Way', 'South Sound'),
    ('98402', 'Tacoma', 'South Sound'),     ('98405', 'Tacoma', 'South Sound'),
    ('98406', 'Tacoma', 'South Sound'),     ('98407', 'Tacoma', 'South Sound'),
    ('98371', 'Puyallup', 'South Sound'),   ('98372', 'Puyallup', 'South Sound'),
    ('98373', 'Puyallup', 'South Sound'),   ('98374', 'Puyallup', 'South Sound'),
    ('98375', 'Puyallup', 'South Sound');
