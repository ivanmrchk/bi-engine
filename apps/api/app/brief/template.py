"""A plain brief assembled from the facts, with no model involved.

Used when there's no OpenAI key, or when drafts keep inventing numbers.
Less readable than a drafted brief, but every word is traceable.
"""

from app.brief.writer import BriefText

READABLE_REASON = {
    "demand": "fewer people asking for work",
    "conversion": "fewer estimates turning into jobs",
    "ticket size": "smaller jobs",
}


def template_brief(sheet: dict) -> BriefText:
    services = sheet["top_services_this_month"]
    struggling = sheet["cities_with_clearly_falling_revenue"]
    calls = sheet["calls_this_month"]
    company = sheet["revenue_vs_same_months_a_year_before"]

    top = services[0] if services else None
    headline = (
        f"{sheet['month']}: {top['service']} led with {top['revenue']} from {top['jobs']} jobs."
        if top else f"{sheet['month']}: no completed jobs."
    )
    summary = f"Revenue over the recent months changed {company['change']} against the same months a year before"
    if company["factors_that_clearly_fell"]:
        summary += f", despite {', '.join(READABLE_REASON[factor] for factor in company['factors_that_clearly_fell'])}."
    else:
        summary += "."
    if calls.get("unanswered_share"):
        summary += f" {calls['unanswered_share']} of calls went unanswered."

    growing = [service for service in services if str(service["change_vs_same_month_last_year"]).startswith("+")]
    opportunity = (
        f"{growing[0]['service']} is up {growing[0]['change_vs_same_month_last_year']} on the same month last year."
        if growing else "No service grew clearly against last year this month."
    )
    risk = (
        f"{struggling[0]['city']} revenue is {struggling[0]['revenue_change']}, "
        f"driven by {READABLE_REASON[struggling[0]['factors_that_clearly_fell'][0]]}."
        if struggling else "No city shows a clear decline."
    )
    return BriefText(headline=headline, summary=summary, biggest_opportunity=opportunity, biggest_risk=risk)
