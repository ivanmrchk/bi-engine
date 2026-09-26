INSERT INTO clean.invoices (invoice_id, job_id, status, amount_cents, invoice_date, service_date, paid_at)
SELECT
    invoice.invoice_id,
    invoice.record->>'job_id',
    invoice.record->>'status',
    (invoice.record->>'amount')::BIGINT,
    (invoice.record->>'invoice_date')::TIMESTAMPTZ,
    (invoice.record->>'service_date')::TIMESTAMPTZ,
    (invoice.record->>'paid_at')::TIMESTAMPTZ
FROM staging.housecall_pro_invoices AS invoice
JOIN clean.jobs AS job ON job.job_id = invoice.record->>'job_id';
