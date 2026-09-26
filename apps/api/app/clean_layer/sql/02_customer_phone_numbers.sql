-- Every number a customer has given on any record, mobile or home, in E.164.
INSERT INTO clean.customer_phone_numbers (phone_e164, customer_id)
SELECT DISTINCT phone.phone_e164, record.customer->>'id'
FROM staging.housecall_pro_customer_records AS record
CROSS JOIN LATERAL (
    VALUES (clean.phone_e164(record.customer->>'mobile_number')),
           (clean.phone_e164(record.customer->>'home_number'))
) AS phone (phone_e164)
WHERE phone.phone_e164 IS NOT NULL;
