-- The original single-table prototype. Kept only so the existing endpoints
-- keep working until the ingestion and analysis layers replace them; a
-- later migration drops it.

CREATE TABLE events (
    id          BIGSERIAL PRIMARY KEY,
    source      TEXT NOT NULL,
    location_id TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    payload     JSONB NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_events_location ON events (location_id);
CREATE INDEX idx_events_type ON events (event_type);
CREATE INDEX idx_events_occurred ON events (occurred_at);
