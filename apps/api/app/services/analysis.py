from sqlalchemy import text
from sqlalchemy.orm import Session


def hot_services(session: Session, month: str) -> list[dict]:
    rows = session.execute(
        text(
            """
            SELECT payload->>'service' AS service,
                   COUNT(*) AS job_count,
                   COALESCE(SUM((payload->>'revenue')::numeric), 0) AS revenue
            FROM events
            WHERE event_type = 'job_completed'
              AND to_char(occurred_at, 'YYYY-MM') = :month
            GROUP BY service
            ORDER BY revenue DESC NULLS LAST
            """
        ),
        {"month": month},
    ).mappings().all()
    return [dict(r) for r in rows]


def lagging_locations(session: Session, month: str, compare_to: str) -> list[dict]:
    rows = session.execute(
        text(
            """
            WITH current AS (
                SELECT location_id, SUM((payload->>'revenue')::numeric) AS revenue
                FROM events
                WHERE event_type = 'job_completed' AND to_char(occurred_at, 'YYYY-MM') = :month
                GROUP BY location_id
            ), previous AS (
                SELECT location_id, SUM((payload->>'revenue')::numeric) AS revenue
                FROM events
                WHERE event_type = 'job_completed' AND to_char(occurred_at, 'YYYY-MM') = :compare_to
                GROUP BY location_id
            )
            SELECT COALESCE(c.location_id, p.location_id) AS location_id,
                   COALESCE(c.revenue, 0) AS current_revenue,
                   COALESCE(p.revenue, 0) AS previous_revenue,
                   COALESCE(c.revenue, 0) - COALESCE(p.revenue, 0) AS delta
            FROM current c
            FULL OUTER JOIN previous p ON c.location_id = p.location_id
            ORDER BY delta ASC
            """
        ),
        {"month": month, "compare_to": compare_to},
    ).mappings().all()
    return [dict(r) for r in rows]


def previous_month(month: str) -> str:
    year, mon = map(int, month.split("-"))
    if mon == 1:
        return f"{year - 1}-12"
    return f"{year}-{mon - 1:02d}"
