"""Reads what the pipeline concluded, from its clean tables."""

from dataclasses import dataclass

import psycopg

from grading.answer_key import LegKey, leg_key


@dataclass(frozen=True)
class SubmissionVerdict:
    submission_id: int
    is_spam: bool
    is_duplicate: bool


@dataclass(frozen=True)
class JobVerdict:
    service: str | None
    location: str | None
    is_real_job: bool


@dataclass(frozen=True)
class PipelineResults:
    submissions: list[SubmissionVerdict]
    jobs: dict[str, JobVerdict]
    call_id_by_leg: dict[LegKey, int]
    call_classification: dict[int, str]


def fetch_pipeline_results(database_url: str) -> PipelineResults:
    with psycopg.connect(database_url) as connection:
        return PipelineResults(
            submissions=[
                SubmissionVerdict(*row)
                for row in connection.execute("""
                    SELECT submission_id, is_spam, duplicate_of_submission_id IS NOT NULL
                    FROM clean.website_submissions
                """)
            ],
            jobs={
                job_id: JobVerdict(service, location, is_real_job)
                for job_id, service, location, is_real_job in connection.execute(
                    "SELECT job_id, service, location_name, is_real_job FROM clean.jobs"
                )
            },
            call_id_by_leg={
                leg_key(started_at, direction, business_line): call_id
                for started_at, direction, business_line, call_id in connection.execute("""
                    SELECT to_char(leg.started_at AT TIME ZONE 'America/Los_Angeles', 'YYYY-MM-DD"T"HH24:MI:SS'),
                           leg.direction, location.business_line, leg.call_id
                    FROM clean.call_legs AS leg
                    JOIN reference.locations AS location USING (location_name)
                """)
            },
            call_classification=dict(connection.execute("SELECT call_id, classification FROM clean.calls")),
        )
