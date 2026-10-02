"""Print the grading report.

    cd evaluation
    python -m grading                                   # ../data/answer_key, local database
    python -m grading --answer-key PATH --database-url URL
"""

import argparse
from pathlib import Path

from grading.answer_key import load_answer_key
from grading.scores import (
    ClassificationReport,
    DetectionScore,
    grade_call_classification,
    grade_call_grouping,
    grade_duplicate_flags,
    grade_jobs,
    grade_spam_filter,
)
from grading.pipeline_results import fetch_pipeline_results
from grading.stories import check_planted_stories

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_URL = "postgresql://postgres:postgres@localhost:5434/bi_engine"


def main() -> None:
    parser = argparse.ArgumentParser(description="Grade the clean layer against the answer key.")
    parser.add_argument("--answer-key", type=Path, default=REPOSITORY_ROOT / "data" / "answer_key")
    parser.add_argument("--database-url", default=DEFAULT_DATABASE_URL)
    arguments = parser.parse_args()

    key = load_answer_key(arguments.answer_key)
    results = fetch_pipeline_results(arguments.database_url)
    if not results.jobs or not results.call_classification:
        raise SystemExit("The clean layer is empty: load the raw files and rebuild it before grading.")

    print("Website submissions")
    _print_detection("spam filter", grade_spam_filter(results, key))
    _print_detection("duplicate flags", grade_duplicate_flags(results, key))

    print("\nHousecall Pro jobs")
    for check, accuracy in grade_jobs(results, key).items():
        print(f"  {check:24} {accuracy.rate:7.1%}  ({accuracy.correct} of {accuracy.total})")

    print("\nCalls")
    whole_calls, split_sessions = grade_call_grouping(results, key)
    print(f"  {'legs grouped into calls':24} {whole_calls.rate:7.1%}  "
          f"({whole_calls.correct} of {whole_calls.total} calls are exactly one conversation; "
          f"{split_sessions} conversations split)")
    _print_classification(grade_call_classification(results, key))

    print("\nPlanted stories found by the analysis")
    for check in check_planted_stories(arguments.answer_key, arguments.database_url):
        print(f"  {'found  ' if check.found else 'MISSED '} {check.story}\n           {check.evidence}")


def _print_detection(name: str, score: DetectionScore) -> None:
    print(f"  {name:24} precision {score.precision:6.1%}  recall {score.recall:6.1%}  "
          f"({score.caught} caught, {score.false_alarms} false alarms, {score.missed} missed)")


def _print_classification(report: ClassificationReport) -> None:
    accuracy = report.accuracy
    print(f"  {'classification':24} {accuracy.rate:7.1%}  ({accuracy.correct} of {accuracy.total} calls)\n")
    print(f"    {'true purpose':26} {'calls':>6} {'recall':>8} {'precision':>10}   most common mistakes")
    for label in report.labels:
        recall, precision = report.recall(label), report.precision(label)
        mistakes = ", ".join(f"{given} ({count})" for given, count in report.top_mistakes(label))
        print(f"    {label:26} {recall.total:6} {recall.rate:8.1%} {precision.rate:10.1%}   {mistakes}")


if __name__ == "__main__":
    main()
