"""relay-engine's uploads are refused unless they carry the shared key.

Every request here is turned away before it reaches the database, and the
client isn't entered as a context manager, so the app's startup (which
connects to Postgres) never runs.
"""

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)
UPLOAD = {"file": ("page_001.json", b'{"leads": []}', "application/json")}


@pytest.fixture
def relay_key(monkeypatch):
    monkeypatch.setattr(settings, "relay_ingest_key", "test-relay-key")


def test_uploads_are_refused_while_no_key_is_configured(monkeypatch):
    monkeypatch.setattr(settings, "relay_ingest_key", None)

    response = client.post("/ingest/website_leads", files=UPLOAD, headers={"X-Relay-Ingest-Key": "anything"})

    assert response.status_code == 503


def test_an_upload_without_the_key_is_refused(relay_key):
    response = client.post("/ingest/website_leads", files=UPLOAD)

    assert response.status_code == 401


def test_an_upload_with_the_wrong_key_is_refused(relay_key):
    response = client.post("/ingest/website_leads", files=UPLOAD, headers={"X-Relay-Ingest-Key": "wrong-key"})

    assert response.status_code == 401


def test_the_right_key_gets_past_the_check(relay_key):
    # An unknown feed is rejected after the key check and before any database work.
    response = client.post("/ingest/no_such_feed", files=UPLOAD, headers={"X-Relay-Ingest-Key": "test-relay-key"})

    assert response.status_code == 404


def test_the_rebuild_after_a_pull_needs_the_key_too(relay_key):
    response = client.post("/ingest/rebuild")

    assert response.status_code == 401
