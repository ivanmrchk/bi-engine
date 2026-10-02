-- btrim() trims only spaces by default, so a value of '\n' or ' \t' wasn't
-- treated as blank. Trim every kind of whitespace.
CREATE OR REPLACE FUNCTION clean.blank_to_null(value TEXT) RETURNS TEXT
LANGUAGE sql IMMUTABLE AS $$
    SELECT NULLIF(btrim(value, E' \t\r\n'), '')
$$;
