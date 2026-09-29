"""Compares the pipeline's conclusions with the truth.

Pure functions: no database, no files, so every grading rule is testable.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass

from grading.answer_key import AnswerKey, TrueCallLeg
from grading.pipeline_results import PipelineResults

LEAD_PURPOSES = {"new_customer_lead", "returning_customer_lead"}


@dataclass(frozen=True)
class Accuracy:
    correct: int
    total: int

    @property
    def rate(self) -> float:
        return self.correct / self.total if self.total else 0.0


@dataclass(frozen=True)
class DetectionScore:
    """For yes/no flags such as spam: what was caught, what was wrongly flagged, what was missed."""

    caught: int
    false_alarms: int
    missed: int

    @property
    def precision(self) -> float:
        flagged = self.caught + self.false_alarms
        return self.caught / flagged if flagged else 1.0

    @property
    def recall(self) -> float:
        actual = self.caught + self.missed
        return self.caught / actual if actual else 1.0


@dataclass(frozen=True)
class ClassificationReport:
    confusion: Counter  # (expected label, pipeline label) -> number of calls

    @property
    def labels(self) -> list[str]:
        return sorted({expected for expected, _ in self.confusion})

    @property
    def accuracy(self) -> Accuracy:
        correct = sum(count for (expected, given), count in self.confusion.items() if expected == given)
        return Accuracy(correct, sum(self.confusion.values()))

    def recall(self, label: str) -> Accuracy:
        """Of the calls that really were `label`, how many the pipeline got right."""
        total = sum(count for (expected, _), count in self.confusion.items() if expected == label)
        return Accuracy(self.confusion[(label, label)], total)

    def precision(self, label: str) -> Accuracy:
        """Of the calls the pipeline called `label`, how many really were."""
        total = sum(count for (_, given), count in self.confusion.items() if given == label)
        return Accuracy(self.confusion[(label, label)], total)

    def top_mistakes(self, label: str, limit: int = 3) -> list[tuple[str, int]]:
        mistakes = Counter({given: count for (expected, given), count in self.confusion.items()
                            if expected == label and given != label})
        return mistakes.most_common(limit)


# --- Website submissions ------------------------------------------------------


def grade_spam_filter(results: PipelineResults, key: AnswerKey) -> DetectionScore:
    is_spam = {submission_id: lead_id is None for submission_id, lead_id in key.true_lead_by_submission.items()}
    return _detection_score((verdict.is_spam, is_spam[verdict.submission_id]) for verdict in results.submissions)


def grade_duplicate_flags(results: PipelineResults, key: AnswerKey) -> DetectionScore:
    """A submission is a duplicate if its true lead already submitted with a lower id."""
    is_duplicate = {}
    leads_seen = set()
    for submission_id in sorted(key.true_lead_by_submission):
        lead_id = key.true_lead_by_submission[submission_id]
        is_duplicate[submission_id] = lead_id is not None and lead_id in leads_seen
        leads_seen.add(lead_id)
    return _detection_score((verdict.is_duplicate, is_duplicate[verdict.submission_id]) for verdict in results.submissions)


def _detection_score(flagged_and_actual) -> DetectionScore:
    tally = Counter(flagged_and_actual)
    return DetectionScore(caught=tally[(True, True)], false_alarms=tally[(True, False)], missed=tally[(False, True)])


# --- Housecall Pro jobs -------------------------------------------------------


def grade_jobs(results: PipelineResults, key: AnswerKey) -> dict[str, Accuracy]:
    graded = [(verdict, key.jobs[job_id]) for job_id, verdict in results.jobs.items()]
    return {
        "real job or not": Accuracy(sum(v.is_real_job == t.is_real_job for v, t in graded), len(graded)),
        "service": Accuracy(sum(v.service == t.service for v, t in graded), len(graded)),
        "location": Accuracy(sum(v.location == t.location for v, t in graded), len(graded)),
    }


# --- Calls ------------------------------------------------------------------


def grade_call_grouping(results: PipelineResults, key: AnswerKey) -> tuple[Accuracy, int]:
    """(calls made of exactly one real conversation, conversations split across calls)."""
    sessions_by_call = defaultdict(set)
    calls_by_session = defaultdict(set)
    for leg, call_id in results.call_id_by_leg.items():
        session_id = key.call_legs[leg].session_id
        sessions_by_call[call_id].add(session_id)
        calls_by_session[session_id].add(call_id)
    whole_calls = sum(1 for sessions in sessions_by_call.values() if len(sessions) == 1)
    split_sessions = sum(1 for calls in calls_by_session.values() if len(calls) > 1)
    return Accuracy(whole_calls, len(sessions_by_call)), split_sessions


def grade_call_classification(results: PipelineResults, key: AnswerKey) -> ClassificationReport:
    first_leg_of_call: dict[int, TrueCallLeg] = {}
    for leg, call_id in sorted(results.call_id_by_leg.items()):
        first_leg_of_call.setdefault(call_id, key.call_legs[leg])

    return ClassificationReport(Counter(
        (expected_call_label(true_leg, key), results.call_classification[call_id])
        for call_id, true_leg in first_leg_of_call.items()
    ))


def expected_call_label(true_leg: TrueCallLeg, key: AnswerKey) -> str:
    """The label the pipeline should give, in the business's terms.

    A lead is a returning customer's only if they were already in Housecall
    Pro; otherwise it's a new customer's if it reached Housecall Pro (a job
    or an estimate), and an unconverted caller's if it never did.
    """
    if true_leg.purpose not in LEAD_PURPOSES:
        return true_leg.purpose
    lead = key.leads[true_leg.lead_id]
    if lead.customer_had_earlier_hcp_record:
        return "returning_customer_lead"
    reached_housecall_pro = lead.outcome != "lost" or lead.had_estimate
    return "new_customer_lead" if reached_housecall_pro else "unconverted_caller"
