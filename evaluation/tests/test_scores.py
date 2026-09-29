from collections import Counter

from grading.answer_key import AnswerKey, TrueCallLeg, TrueLead
from grading.scores import ClassificationReport, expected_call_label


def answer_key_with_lead(lead: TrueLead) -> AnswerKey:
    return AnswerKey(leads={lead.lead_id: lead}, jobs={}, call_legs={}, true_lead_by_submission={})


def lead(outcome="completed", had_estimate=False, customer_had_earlier_hcp_record=False) -> TrueLead:
    return TrueLead("lead_1", outcome, had_estimate, customer_had_earlier_hcp_record)


def lead_call(purpose="new_customer_lead") -> TrueCallLeg:
    return TrueCallLeg(session_id="1", purpose=purpose, lead_id="lead_1")


def test_a_lead_that_booked_is_a_new_customer_lead():
    key = answer_key_with_lead(lead(outcome="completed"))

    assert expected_call_label(lead_call(), key) == "new_customer_lead"


def test_a_lost_lead_that_was_quoted_still_reached_housecall_pro():
    key = answer_key_with_lead(lead(outcome="lost", had_estimate=True))

    assert expected_call_label(lead_call(), key) == "new_customer_lead"


def test_a_lost_lead_that_was_never_quoted_is_an_unconverted_caller():
    key = answer_key_with_lead(lead(outcome="lost", had_estimate=False))

    assert expected_call_label(lead_call(), key) == "unconverted_caller"


def test_coming_back_without_an_earlier_hcp_record_is_not_returning():
    key = answer_key_with_lead(lead(outcome="completed", customer_had_earlier_hcp_record=False))

    assert expected_call_label(lead_call("returning_customer_lead"), key) == "new_customer_lead"


def test_coming_back_with_an_earlier_hcp_record_is_returning():
    key = answer_key_with_lead(lead(outcome="lost", customer_had_earlier_hcp_record=True))

    assert expected_call_label(lead_call("returning_customer_lead"), key) == "returning_customer_lead"


def test_non_lead_purposes_are_expected_as_they_are():
    key = answer_key_with_lead(lead())

    assert expected_call_label(lead_call("business_contact"), key) == "business_contact"


def test_precision_and_recall_count_from_different_sides_of_the_matrix():
    report = ClassificationReport(Counter({
        ("spam", "spam"): 8,
        ("spam", "unconverted_caller"): 2,  # missed spam: hurts spam's recall
        ("unconverted_caller", "spam"): 4,  # false alarm: hurts spam's precision
    }))

    assert report.recall("spam").rate == 8 / 10
    assert report.precision("spam").rate == 8 / 12
    assert report.accuracy.correct == 8
