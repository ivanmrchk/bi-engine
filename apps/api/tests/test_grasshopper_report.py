import pytest

from app.ingestion.grasshopper_report import NotAGrasshopperReport, parse_grasshopper_report

REPORT = """Report: Usage Totals:
Total Minutes (Inbound),Total Minutes (Outbound),Total Minutes (Inbound + Outbound)
3,2,5


Report: Detail_09.25.2026_18.50.53_PM
Date/Time,VPS Number,Duration,Caller ID,Connecting #,Extension,Direction,Type
9/25/2026 4:54:11 PM,(425) 555-0100,="2:12",(206) 555-4431,Unknown,0 - Default Extension,In,Inbound leg of forwarded call
9/25/2026 4:54:22 PM,(425) 555-0100,="2:00",Unknown,(360) 555-0100,0 - Default Extension,Out,Forwarded call connected


"""


def test_skips_the_usage_totals_and_trailing_blank_lines():
    rows = parse_grasshopper_report(REPORT)

    assert len(rows) == 2


def test_keeps_values_exactly_as_written():
    _, first_row = parse_grasshopper_report(REPORT)[0]

    assert first_row["Duration"] == '="2:12"'
    assert first_row["Connecting #"] == "Unknown"
    assert first_row["Date/Time"] == "9/25/2026 4:54:11 PM"


def test_line_numbers_match_the_original_file():
    line_numbers = [line_number for line_number, _ in parse_grasshopper_report(REPORT)]

    assert line_numbers == [8, 9]
    assert REPORT.splitlines()[8 - 1].startswith("9/25/2026 4:54:11 PM")


def test_a_week_without_calls_has_no_rows():
    header_only = REPORT.split("9/25/2026")[0]

    assert parse_grasshopper_report(header_only) == []


def test_rejects_a_file_that_is_not_a_call_report():
    with pytest.raises(NotAGrasshopperReport):
        parse_grasshopper_report("name,phone\nAda,555-0100\n")
