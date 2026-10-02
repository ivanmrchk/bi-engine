from app.brief.guard import invented_numbers
from app.brief.template import template_brief

SOURCE = '{"revenue": "$45,221", "revenue_change": "-42%", "jobs": 12, "share": "0.5"}'


def test_numbers_copied_from_the_source_pass():
    assert invented_numbers("Revenue was $45,221 from 12 jobs.", SOURCE) == []


def test_formatting_differences_still_match():
    # no thousands separator, no sign, trailing zero
    assert invented_numbers("Revenue of 45221, down 42%, a share of 0.50.", SOURCE) == []


def test_a_number_not_in_the_source_is_invented():
    assert invented_numbers("Revenue was $45,221, about $3,800 per job.", SOURCE) == ["3,800"]


def test_each_invented_number_is_reported_once():
    assert invented_numbers("Up 17%, then 17% again.", SOURCE) == ["17"]


def facts_sheet(struggling=None, services=None) -> dict:
    return {
        "month": "August 2026",
        "top_services_this_month": services if services is not None else [
            {"service": "Panel Upgrade", "jobs": 7, "revenue": "$43,872", "change_vs_same_month_last_year": "+18%"},
        ],
        "revenue_vs_same_months_a_year_before": {
            "months_compared": 6, "change": "+12%", "factor_changes": {}, "factors_that_clearly_fell": ["ticket size"],
        },
        "cities_with_clearly_falling_revenue": struggling or [],
        "calls_this_month": {"unanswered_share": "15%"},
    }


def test_the_template_names_the_worst_city_and_its_reason():
    sheet = facts_sheet(struggling=[
        {"city": "Bellevue", "revenue_change": "-42%", "factors_that_clearly_fell": ["conversion"]},
    ])

    assert template_brief(sheet).biggest_risk == "Bellevue revenue is -42%, driven by fewer estimates turning into jobs."


def test_the_template_only_states_numbers_from_the_facts():
    sheet = facts_sheet(struggling=[
        {"city": "Bellevue", "revenue_change": "-42%", "factors_that_clearly_fell": ["conversion"]},
    ])

    assert invented_numbers(template_brief(sheet).as_text(), str(sheet)) == []


def test_a_month_without_jobs_still_gets_a_brief():
    assert template_brief(facts_sheet(services=[])).headline == "August 2026: no completed jobs."
