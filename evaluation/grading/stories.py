"""Checks that the pipeline's analyses find the stories planted in the data.

The checks call the pipeline's own analysis functions, unchanged, against
a database the pipeline built, and compare what they report with what the
generator planted. The pipeline never sees the answer key; only these
checks do.
"""

import csv
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from sqlalchemy import Connection, create_engine

# The pipeline's source lives in apps/api; import its analysis code as-is.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))

from app.analysis.call_handling import call_handling_by_month  # noqa: E402
from app.analysis.channel_funnel import channel_funnel  # noqa: E402
from app.analysis.city_diagnosis import diagnose_cities  # noqa: E402
from app.analysis.months import add_months  # noqa: E402

# Which reason each kind of planted story should produce.
REASON_FOR_EFFECT = {
    "lead_share_multiplier": "demand",
    "estimate_only_multiplier": "conversion",
    "ticket_price_multiplier": "ticket size",
}
DIAGNOSIS_WINDOW_MONTHS = 6


@dataclass(frozen=True)
class StoryCheck:
    story: str
    found: bool
    evidence: str


def check_planted_stories(answer_key_dir: Path, database_url: str) -> list[StoryCheck]:
    facts = _read_facts(answer_key_dir / "company_facts.csv")
    last_month = date.fromisoformat(facts["last_simulated_month"])
    engine = create_engine(database_url.replace("postgresql://", "postgresql+psycopg://", 1))
    with engine.connect() as connection:
        return [
            *_city_story_checks(connection, answer_key_dir / "planted_stories.csv", last_month),
            _ai_call_taker_check(connection, date.fromisoformat(facts["ai_call_taker_adopted_on"])),
            _chatgpt_growth_check(connection, last_month),
        ]


def _city_story_checks(connection: Connection, stories_file: Path, last_month: date) -> list[StoryCheck]:
    report = diagnose_cities(connection, last_month, DIAGNOSIS_WINDOW_MONTHS)
    diagnosis_by_city = {city.city: city for city in report.cities}
    checks = []
    for story in _read_rows(stories_file):
        expected_reason = next(REASON_FOR_EFFECT[effect] for effect in REASON_FOR_EFFECT if float(story[effect]) != 1.0)
        diagnosis = diagnosis_by_city[story["city"]]
        checks.append(StoryCheck(
            story=f"{story['city']}: {story['what_happened']} -> {expected_reason}",
            found=expected_reason in diagnosis.reasons,
            evidence=f"revenue {diagnosis.revenue_change:+.0%}, reasons found: {', '.join(diagnosis.reasons) or 'none'}",
        ))
    return checks


def _ai_call_taker_check(connection: Connection, adopted_on: date) -> StoryCheck:
    """Unanswered calls should at least halve once the AI call taker answers them."""
    adoption_month = adopted_on.replace(day=1)
    before = call_handling_by_month(connection, add_months(adoption_month, -4), add_months(adoption_month, -1))
    after = call_handling_by_month(connection, adoption_month, add_months(adoption_month, 3))
    share_before = sum(month.unanswered for month in before) / sum(month.calls for month in before)
    share_after = sum(month.unanswered for month in after) / sum(month.calls for month in after)
    return StoryCheck(
        story=f"AI call taker adopted {adoption_month:%B %Y} -> fewer unanswered calls",
        found=share_after <= share_before / 2,
        evidence=f"unanswered {share_before:.0%} in the 4 months before, {share_after:.0%} in the 4 months after",
    )


def _chatgpt_growth_check(connection: Connection, last_month: date) -> StoryCheck:
    """AI search went from almost nothing to a real channel: at least 3x the
    leads in the last year of history compared with the first."""
    first_year = channel_funnel(connection, add_months(last_month, -35), add_months(last_month, -24))
    last_year = channel_funnel(connection, add_months(last_month, -11), last_month)
    leads_first_year = _channel_leads(first_year, "chatgpt")
    leads_last_year = _channel_leads(last_year, "chatgpt")
    return StoryCheck(
        story="ChatGPT grows into a lead channel",
        found=leads_last_year >= 3 * max(leads_first_year, 1),
        evidence=f"{leads_first_year} ChatGPT leads in the first year, {leads_last_year} in the last",
    )


def _channel_leads(report, channel: str) -> int:
    return next((funnel.leads for funnel in report.channels if funnel.channel == channel), 0)


def _read_facts(path: Path) -> dict[str, str]:
    return {row["fact"]: row["value"] for row in _read_rows(path)}


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))
