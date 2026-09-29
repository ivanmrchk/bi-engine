-- One row per stored Grasshopper export: when it was exported and which
-- calls it contains. The export doesn't say which date range was chosen,
-- but Grasshopper names the file after the moment of export
-- ('Detail_09.25.2026_18.50.53_PM.csv', a 24-hour clock plus AM/PM), so
-- no call after that moment can be in it. A renamed file falls back to
-- its latest call.

CREATE VIEW staging.grasshopper_exports AS
SELECT
    file.file_id,
    file.file_name,
    CASE
        WHEN file.file_name ~ '^Detail_\d{2}\.\d{2}\.\d{4}_\d{2}\.\d{2}\.\d{2}_(AM|PM)\.csv$'
        THEN to_timestamp(substring(file.file_name FROM 8 FOR 19), 'MM.DD.YYYY_HH24.MI.SS')::TIMESTAMP
             AT TIME ZONE 'America/Los_Angeles'
    END AS exported_at,
    min(clean.from_pacific_wall_clock(csv_row.fields->>'Date/Time')) AS first_call_at,
    max(clean.from_pacific_wall_clock(csv_row.fields->>'Date/Time')) AS last_call_at
FROM raw.ingested_files AS file
LEFT JOIN raw.csv_rows AS csv_row USING (file_id)
WHERE file.feed = 'grasshopper_calls'
GROUP BY file.file_id, file.file_name;
