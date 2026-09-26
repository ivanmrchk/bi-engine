"""Generate the synthetic dataset.

    cd generator
    python -m synthetic_data                  # seed 42, writes to ../data
    python -m synthetic_data --seed 7 --data-dir /tmp/data
"""

import argparse
from pathlib import Path

from synthetic_data.calibration import COMPANY_NAME
from synthetic_data.dataset import Dataset, build_dataset
from synthetic_data.writer import write_dataset

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SEED = 42


def main() -> None:
    parser = argparse.ArgumentParser(description=f"Generate the synthetic {COMPANY_NAME} dataset.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED,
                        help="the same seed always produces the same dataset (default: %(default)s)")
    parser.add_argument("--data-dir", type=Path, default=REPOSITORY_ROOT / "data",
                        help="where to write raw/ and answer_key/ (default: %(default)s)")
    arguments = parser.parse_args()

    dataset = build_dataset(arguments.seed)
    write_dataset(dataset, arguments.data_dir)
    _print_summary(dataset, arguments.data_dir)


def _print_summary(dataset: Dataset, data_dir: Path) -> None:
    history = dataset.history
    call_rows = sum(len(session.legs) for session in dataset.call_sessions)
    website_submissions = len(dataset.website_leads.true_lead_id_by_submission_id)
    print(f"Wrote the {COMPANY_NAME} dataset to {data_dir}")
    print(f"  truth:          {len(history.customers)} customers, {len(history.leads)} leads, "
          f"{len(history.estimates)} estimates, {len(history.jobs)} jobs")
    print(f"  housecall_pro:  jobs, invoices, and estimates as paginated JSON")
    print(f"  grasshopper:    {len(dataset.grasshopper_reports)} weekly CSV exports ({call_rows} call legs)")
    print(f"  website_leads:  {website_submissions} form submissions")
    print(f"  search_console: {len(dataset.search_console_days)} days")


if __name__ == "__main__":
    main()
