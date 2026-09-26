"""Reads Grasshopper's call-detail CSV export.

The file is two reports stacked in one: a "Usage Totals" summary first,
then the call detail. Only the detail matters, so parsing starts at its
header line. Values are returned exactly as written ('="2:12"',
'Unknown'); interpreting them is the clean layer's job.
"""

import csv

DETAIL_HEADER_START = "Date/Time,"


class NotAGrasshopperReport(ValueError):
    pass


def parse_grasshopper_report(text: str) -> list[tuple[int, dict[str, str]]]:
    """Every call-detail row, as (line number in the file, {column: value})."""
    lines = text.splitlines()
    header_index = _find_detail_header(lines)

    reader = csv.DictReader(lines[header_index:])
    rows = []
    for fields in reader:
        if not any(fields.values()):
            continue
        # reader.line_num counts from the header, so offset it to the file's own numbering.
        rows.append((header_index + reader.line_num, fields))
    return rows


def _find_detail_header(lines: list[str]) -> int:
    for index, line in enumerate(lines):
        if line.startswith(DETAIL_HEADER_START):
            return index
    raise NotAGrasshopperReport("No call-detail header ('Date/Time,...') found in the file")
