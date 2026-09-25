"""Generate a synthetic multi-location, multi-month dataset and post it
to the running API's /ingest endpoint. Mirrors the shape of real
GBP/call-tracking/CRM data without using any real client data.

Usage:
    API_URL=http://localhost:8000 python scripts/generate_synthetic_data.py
"""

import os
import random
from datetime import datetime, timedelta

import requests

API_URL = os.environ.get("API_URL", "http://localhost:8000")

LOCATIONS = ["austin-tx", "dallas-tx", "phoenix-az", "tampa-fl", "denver-co"]
SERVICES = ["hvac-repair", "plumbing", "electrical", "roofing", "pest-control"]
SERVICE_WEIGHTS = [3, 3, 2, 1, 1]


def random_timestamp(year: int, month: int) -> datetime:
    day = random.randint(1, 28)
    return datetime(year, month, day, random.randint(7, 18), random.randint(0, 59))


def generate(months: int = 6, jobs_per_month: int = 40) -> list[dict]:
    now = datetime.utcnow().replace(day=1)
    events = []
    for i in range(months):
        month_date = now - timedelta(days=30 * i)
        year, month = month_date.year, month_date.month
        for _ in range(jobs_per_month):
            location = random.choice(LOCATIONS)
            service = random.choices(SERVICES, weights=SERVICE_WEIGHTS)[0]
            revenue = round(random.uniform(150, 2200), 2)
            occurred = random_timestamp(year, month)
            events.append(
                {
                    "source": "housecall_pro",
                    "location_id": location,
                    "event_type": "job_completed",
                    "occurred_at": occurred.isoformat(),
                    "payload": {"service": service, "revenue": revenue},
                }
            )
    return events


def main() -> None:
    events = generate()
    print(f"Posting {len(events)} synthetic events to {API_URL}/ingest ...")
    for event in events:
        resp = requests.post(f"{API_URL}/ingest", json=event, timeout=10)
        resp.raise_for_status()
    months = sorted({e["occurred_at"][:7] for e in events})
    print("Done. Try, e.g.:")
    print(f"  GET {API_URL}/analysis/hot-services?month={months[-1]}")
    print(f"  GET {API_URL}/analysis/lagging-locations?month={months[-1]}")
    print(f"  GET {API_URL}/brief/{LOCATIONS[0]}?month={months[-1]}")


if __name__ == "__main__":
    main()
