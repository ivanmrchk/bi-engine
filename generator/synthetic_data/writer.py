"""Writes a dataset to disk, each source in the layout its real export uses.

    data/raw/            what the pipeline ingests
    data/answer_key/     the hidden truth, read only when grading the pipeline

Both folders are replaced on every run so no stale file from an earlier
run can linger (Grasshopper file names depend on export times, for one).
"""

import csv
import json
import shutil
from pathlib import Path

from synthetic_data.dataset import Dataset


def write_dataset(dataset: Dataset, data_dir: Path) -> None:
    raw_dir = data_dir / "raw"
    answer_key_dir = data_dir / "answer_key"
    for directory in (raw_dir, answer_key_dir):
        shutil.rmtree(directory, ignore_errors=True)

    _write_raw_files(dataset, raw_dir)
    _write_answer_key(dataset, answer_key_dir)


# --- What the pipeline sees ----------------------------------------------


def _write_raw_files(dataset: Dataset, raw_dir: Path) -> None:
    housecall_pro_dir = raw_dir / "housecall_pro"
    _write_pages(housecall_pro_dir / "jobs", dataset.housecall_pro.job_pages)
    _write_pages(housecall_pro_dir / "invoices", dataset.housecall_pro.invoice_pages)
    _write_pages(housecall_pro_dir / "estimates", dataset.housecall_pro.estimate_pages)

    for report in dataset.grasshopper_reports:
        _write_text(raw_dir / "grasshopper" / report.file_name, report.content)

    _write_pages(raw_dir / "website_leads", dataset.website_leads.pages)

    search_console_dir = raw_dir / "search_console"
    for search_day in dataset.search_console_days:
        file_name = f"{search_day.day.isoformat()}.json"
        _write_json(search_console_dir / "by_date" / file_name, search_day.totals_response)
        _write_json(search_console_dir / "by_query_page" / file_name, search_day.query_page_response)


def _write_pages(directory: Path, pages: list[dict]) -> None:
    for page_number, page in enumerate(pages, start=1):
        _write_json(directory / f"page_{page_number:03d}.json", page)


# --- The truth, for grading ------------------------------------------------


def _write_answer_key(dataset: Dataset, answer_key_dir: Path) -> None:
    _write_csv(
        answer_key_dir / "leads.csv",
        ("lead_id", "customer_id", "location", "city", "service", "marketing_channel",
         "contact_method", "created_at", "outcome", "is_returning_customer"),
        (
            (lead.lead_id, lead.customer.customer_id, lead.customer.location.name,
             lead.customer.service_area.city, lead.service.name, lead.marketing_channel.name,
             lead.contact_method, lead.created_at.isoformat(), lead.outcome, lead.is_returning_customer)
            for lead in dataset.history.leads
        ),
    )
    _write_csv(
        answer_key_dir / "call_legs.csv",
        ("session_id", "purpose", "external_number", "customer_id", "lead_id",
         "started_at", "business_line", "direction", "leg_type"),
        (
            (session_id, session.purpose, session.external_number, session.customer_id or "",
             session.lead_id or "", leg.started_at.isoformat(), leg.business_line, leg.direction, leg.leg_type)
            for session_id, session in enumerate(dataset.call_sessions, start=1)
            for leg in session.legs
        ),
    )
    _write_csv(
        answer_key_dir / "website_submissions.csv",
        ("submission_id", "true_lead_id"),
        (
            (submission_id, true_lead_id or "")
            for submission_id, true_lead_id in dataset.website_leads.true_lead_id_by_submission_id.items()
        ),
    )


# --- File helpers ----------------------------------------------------------


def _write_json(path: Path, data: dict) -> None:
    """Compact, the way APIs send it; pretty-print when reading if needed."""
    _write_text(path, json.dumps(data, ensure_ascii=False))


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="")


def _write_csv(path: Path, header: tuple[str, ...], rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(header)
        writer.writerows(rows)
