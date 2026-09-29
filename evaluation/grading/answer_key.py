"""Reads the generator's answer key: what really happened."""

import csv
from dataclasses import dataclass
from pathlib import Path

# A call leg is identified by when (Pacific wall clock, to the second), which
# way it went, and which business line it was on.
LegKey = tuple[str, str, str]


@dataclass(frozen=True)
class TrueLead:
    lead_id: str
    outcome: str
    had_estimate: bool
    customer_had_earlier_hcp_record: bool


@dataclass(frozen=True)
class TrueJob:
    job_id: str
    service: str
    location: str
    is_real_job: bool


@dataclass(frozen=True)
class TrueCallLeg:
    session_id: str
    purpose: str
    lead_id: str


@dataclass(frozen=True)
class AnswerKey:
    leads: dict[str, TrueLead]
    jobs: dict[str, TrueJob]
    call_legs: dict[LegKey, TrueCallLeg]
    true_lead_by_submission: dict[int, str | None]  # None means spam


def load_answer_key(directory: Path) -> AnswerKey:
    return AnswerKey(
        leads={
            row["lead_id"]: TrueLead(
                lead_id=row["lead_id"],
                outcome=row["outcome"],
                had_estimate=row["had_estimate"] == "True",
                customer_had_earlier_hcp_record=row["customer_had_earlier_hcp_record"] == "True",
            )
            for row in _read_csv(directory / "leads.csv")
        },
        jobs={
            row["job_id"]: TrueJob(row["job_id"], row["service"], row["location"], row["is_real_job"] == "True")
            for row in _read_csv(directory / "jobs.csv")
        },
        call_legs={
            leg_key(row["started_at"], row["direction"], row["business_line"]):
                TrueCallLeg(row["session_id"], row["purpose"], row["lead_id"])
            for row in _read_csv(directory / "call_legs.csv")
        },
        true_lead_by_submission={
            int(row["submission_id"]): row["true_lead_id"] or None
            for row in _read_csv(directory / "website_submissions.csv")
        },
    )


def leg_key(started_at: str, direction: str, business_line: str) -> LegKey:
    """'2023-09-08T14:27:56-07:00' and '2023-09-08T14:27:56' name the same second."""
    return started_at[:19], direction.lower(), business_line


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))
