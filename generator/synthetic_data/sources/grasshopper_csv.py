"""Grasshopper's call-detail report, exported by hand about once a week.

Each export is "the last 7 days" as of whenever someone remembered to run
it, so consecutive files overlap, and a call near a file boundary can have
its legs split across two files. The layout copies the real export: a
usage-totals section first, then the detail rows, newest first.
"""

import random
from dataclasses import dataclass
from datetime import datetime, time, timedelta

from synthetic_data.sources.grasshopper_calls import CallLeg, CallSession, Direction
from synthetic_data.timeline import BUSINESS_TIMEZONE, simulated_days

EXPORT_WINDOW = timedelta(days=7)
FEWEST_DAYS_BETWEEN_EXPORTS = 4
MOST_DAYS_BETWEEN_EXPORTS = 7

USAGE_TOTALS_HEADER = "Total Minutes (Inbound),Total Minutes (Outbound),Total Minutes (Inbound + Outbound)"
DETAIL_HEADER = "Date/Time,VPS Number,Duration,Caller ID,Connecting #,Extension,Direction,Type"


@dataclass(frozen=True)
class ExportFile:
    file_name: str
    content: str


def export_grasshopper_reports(sessions: list[CallSession], randomness: random.Random) -> list[ExportFile]:
    legs_newest_first = _legs_in_report_order(sessions)
    return [_report(exported_at, legs_newest_first) for exported_at in _export_moments(randomness)]


def _export_moments(randomness: random.Random) -> list[datetime]:
    """Roughly weekly, at a random time of day, until the history is covered."""
    days = simulated_days()
    first_export_day = days[0] + EXPORT_WINDOW
    history_ends_at = datetime.combine(days[-1] + timedelta(days=1), time(0), tzinfo=BUSINESS_TIMEZONE)

    moments = []
    export_day = first_export_day
    while True:
        exported_at = datetime.combine(
            export_day,
            time(randomness.randint(8, 19), randomness.randint(0, 59), randomness.randint(0, 59)),
            tzinfo=BUSINESS_TIMEZONE,
        )
        moments.append(exported_at)
        if exported_at >= history_ends_at:
            return moments
        export_day += timedelta(days=randomness.randint(FEWEST_DAYS_BETWEEN_EXPORTS, MOST_DAYS_BETWEEN_EXPORTS))


def _legs_in_report_order(sessions: list[CallSession]) -> list[CallLeg]:
    """Newest call first, with each call's legs kept together in the order they happened."""
    newest_first = sorted(sessions, key=lambda session: session.legs[0].started_at, reverse=True)
    return [leg for session in newest_first for leg in session.legs]


def _report(exported_at: datetime, legs_newest_first: list[CallLeg]) -> ExportFile:
    window_start = exported_at - EXPORT_WINDOW
    legs = [leg for leg in legs_newest_first if window_start <= leg.started_at < exported_at]
    report_name = f"Detail_{exported_at:%m.%d.%Y_%H.%M.%S_%p}"

    inbound_minutes = _total_minutes(legs, Direction.IN)
    outbound_minutes = _total_minutes(legs, Direction.OUT)
    lines = [
        "Report: Usage Totals:",
        USAGE_TOTALS_HEADER,
        f"{inbound_minutes},{outbound_minutes},{inbound_minutes + outbound_minutes}",
        "",
        "",
        f"Report: {report_name}",
        DETAIL_HEADER,
        *[_detail_row(leg) for leg in legs],
        "",
        "",
    ]
    return ExportFile(file_name=f"{report_name}.csv", content="\n".join(lines))


def _total_minutes(legs: list[CallLeg], direction: Direction) -> int:
    return round(sum(leg.billed_seconds for leg in legs if leg.direction is direction) / 60)


def _detail_row(leg: CallLeg) -> str:
    """One CSV line. No field ever contains a comma, so a plain join is exact."""
    return ",".join((
        _local_date_time(leg.started_at),
        _display_phone(leg.business_line),
        _excel_wrapped_duration(leg.billed_seconds),
        _display_phone(leg.caller_id),
        _display_phone(leg.connecting_number),
        leg.extension,
        leg.direction,
        leg.leg_type,
    ))


def _local_date_time(moment: datetime) -> str:
    """9/25/2026 4:54:11 PM: local time, no leading zeros, no timezone."""
    local = moment.astimezone(BUSINESS_TIMEZONE)
    hour_on_12_hour_clock = local.hour % 12 or 12
    return f"{local.month}/{local.day}/{local.year} {hour_on_12_hour_clock}:{local:%M:%S %p}"


def _display_phone(e164_phone: str | None) -> str:
    if e164_phone is None:
        return "Unknown"
    return f"({e164_phone[2:5]}) {e164_phone[5:8]}-{e164_phone[8:]}"


def _excel_wrapped_duration(seconds: int) -> str:
    """="2:12", the formula trick that stops Excel reading 2:12 as a time of day."""
    minutes, remaining_seconds = divmod(seconds, 60)
    return f'="{minutes}:{remaining_seconds:02d}"'
