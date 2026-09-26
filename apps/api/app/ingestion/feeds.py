"""The feeds the pipeline ingests: where their files live and what format they're in.

A feed is one stream of same-shaped files from one source. Feed names must
match the CHECK list on raw.ingested_files.feed.
"""

from dataclasses import dataclass
from enum import StrEnum


class FileFormat(StrEnum):
    JSON = "json"
    GRASSHOPPER_REPORT = "grasshopper_report"


@dataclass(frozen=True)
class Feed:
    name: str
    folder: str  # relative to the raw data directory
    file_pattern: str
    file_format: FileFormat


HOUSECALL_PRO_JOBS = Feed("housecall_pro_jobs", "housecall_pro/jobs", "page_*.json", FileFormat.JSON)
HOUSECALL_PRO_INVOICES = Feed("housecall_pro_invoices", "housecall_pro/invoices", "page_*.json", FileFormat.JSON)
HOUSECALL_PRO_ESTIMATES = Feed("housecall_pro_estimates", "housecall_pro/estimates", "page_*.json", FileFormat.JSON)
GRASSHOPPER_CALLS = Feed("grasshopper_calls", "grasshopper", "Detail_*.csv", FileFormat.GRASSHOPPER_REPORT)
WEBSITE_LEADS = Feed("website_leads", "website_leads", "page_*.json", FileFormat.JSON)
SEARCH_CONSOLE_TOTALS = Feed("search_console_totals", "search_console/by_date", "*.json", FileFormat.JSON)
SEARCH_CONSOLE_QUERY_PAGES = Feed(
    "search_console_query_pages", "search_console/by_query_page", "*.json", FileFormat.JSON
)

FEEDS = (
    HOUSECALL_PRO_JOBS,
    HOUSECALL_PRO_INVOICES,
    HOUSECALL_PRO_ESTIMATES,
    GRASSHOPPER_CALLS,
    WEBSITE_LEADS,
    SEARCH_CONSOLE_TOTALS,
    SEARCH_CONSOLE_QUERY_PAGES,
)
