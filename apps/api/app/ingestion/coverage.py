"""Which stretches of time no Grasshopper export covers.

Weekly exports are taken by hand as "the last 7 days". Taken exactly a
week apart but later in the day, they leave a few hours that no file
contains, and any calls in those hours are silently lost. A stretch is
reported when an export's first call comes after every earlier export
was taken; re-exporting that range recovers whatever is missing.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Connection, text


@dataclass(frozen=True)
class CoverageGap:
    missing_from: datetime
    missing_until: datetime
    next_export: str


@dataclass(frozen=True)
class CallCoverage:
    exports: int
    first_call_at: datetime | None
    covered_until: datetime | None
    gaps: list[CoverageGap]


def call_coverage(connection: Connection) -> CallCoverage:
    summary = connection.execute(text("""
        SELECT count(*), min(first_call_at), max(coalesce(exported_at, last_call_at))
        FROM staging.grasshopper_exports
    """)).one()
    return CallCoverage(
        exports=summary[0],
        first_call_at=summary[1],
        covered_until=summary[2],
        gaps=_find_gaps(connection),
    )


def _find_gaps(connection: Connection) -> list[CoverageGap]:
    rows = connection.execute(text("""
        WITH exports AS (
            SELECT file_name, first_call_at, coalesce(exported_at, last_call_at) AS covered_until
            FROM staging.grasshopper_exports
            WHERE first_call_at IS NOT NULL
        ),
        in_order AS (
            SELECT
                file_name,
                first_call_at,
                max(covered_until) OVER (
                    ORDER BY first_call_at
                    ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                ) AS covered_until_by_earlier_exports
            FROM exports
        )
        SELECT covered_until_by_earlier_exports, first_call_at, file_name
        FROM in_order
        WHERE first_call_at > covered_until_by_earlier_exports
        ORDER BY covered_until_by_earlier_exports
    """))
    return [CoverageGap(missing_from, missing_until, next_export) for missing_from, missing_until, next_export in rows]
