-- A customer is retyped on every job and estimate. Name and email come
-- from their most recent record; first_seen_at from their earliest one.
INSERT INTO clean.customers (customer_id, first_name, last_name, email, first_seen_at)
SELECT DISTINCT ON (customer->>'id')
    customer->>'id',
    clean.blank_to_null(customer->>'first_name'),
    clean.blank_to_null(customer->>'last_name'),
    lower(clean.blank_to_null(customer->>'email')),
    min(recorded_at) OVER (PARTITION BY customer->>'id')
FROM staging.housecall_pro_customer_records
ORDER BY customer->>'id', recorded_at DESC;
