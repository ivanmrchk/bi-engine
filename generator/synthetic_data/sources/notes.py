"""What people wrote down: technicians' job notes and the owner's monthly notes.

The text the RAG layer searches. Notes echo what really happened,
including the planted stories, the way people actually notice things:
late, partially, and in passing.
"""

import random
from collections import Counter
from datetime import date

from synthetic_data.calibration import CITY_STORIES, COMPETITOR_NAME, SOUTH_SOUND
from synthetic_data.city_stories import city_story_in_effect
from synthetic_data.jobs import CompanyHistory, Job, LeadOutcome
from synthetic_data.sources.grasshopper_calls import AI_CALL_TAKER_ADOPTED_ON
from synthetic_data.timeline import add_months, simulated_months

SHARE_OF_COMPLETED_JOBS_WITH_A_NOTE = 0.6
SHARE_OF_CANCELED_JOBS_WITH_A_NOTE = 0.5
SHARE_OF_MONTHS_WITH_AN_OPERATIONS_NOTE = 0.4
CHATGPT_NOTICED_ON = date(2025, 10, 1)

WORK_NOTES = {
    "No-Power Troubleshooting": ("Found a loose neutral at the panel, tightened and tested.",
                                 "Tripped main from a failed breaker, replaced it.",
                                 "Half the house out: burned splice in a junction box, repaired."),
    "Outlet & Switch Installation": ("Added three outlets in the basement on a new circuit.",
                                     "Swapped switches to dimmers in living and dining room."),
    "Light Fixture Installation": ("Installed eight recessed cans with dimmer.",
                                   "Hung chandelier, needed a brace in the ceiling."),
    "Diagnostic Visit": ("Flicker traced to a loose connection on the dryer circuit.",
                         "Burning smell from an old outlet, replaced it and checked the run."),
    "EV Charger Installation": ("Installed Tesla wall connector on a new 60A circuit.",
                                "Level 2 charger in garage, panel had room for the breaker."),
    "Panel Upgrade": ("Replaced Zinsco panel with 200A, permit pulled, inspection passed.",
                      "Service upgrade to 200A for the new heat pump."),
    "Heated Floor Wiring": ("Wired bathroom floor heat and thermostat, GFCI protected.",),
    "Commercial Electrical Work": ("Office lighting retrofit to LED, after hours.",
                                   "Added two dedicated circuits for kitchen equipment."),
    "Generator Installation": ("Installed generator inlet and interlock kit.",
                               "Standby generator hooked up, walked owner through the transfer switch."),
    "Hot Tub Wiring": ("Ran 50A circuit and disconnect for the hot tub.",),
    "Circuit Breaker Replacement": ("Replaced two worn breakers.", "Swapped to AFCI breakers in bedrooms."),
}
ESTIMATE_DECLINED_NOTES = ("Customer wants to get a couple more quotes.",
                           "Price was more than they expected, said they'd call back.",
                           "Customer is going to think it over.")
COMPETITOR_DECLINED_NOTES = (f"Customer has a lower quote from {COMPETITOR_NAME}.",
                             f"Went with {COMPETITOR_NAME}, said they were a lot cheaper.")
CANCELED_NOTES = ("Customer canceled, fixed it themselves.",
                  "Canceled the day before, didn't say why.",
                  "Customer's contractor is handling it now.")
SMALL_JOB_NOTES = ("Small job, swapped two light fixtures.", "Quick visit, replaced one outlet.")

SEASONAL_NOTES = {
    1: ("Storm outages kept us busy the first two weeks.", "Cold snap, lots of no-heat and no-power calls."),
    2: ("Slow month, as February always is.", "Quiet February, caught up on paperwork."),
    3: ("Spring remodel season starting.", "Things picking up with remodels."),
    4: ("Hot tub season starting early.", "Lots of outdoor outlet requests."),
    5: ("EV charger quotes picking up.", "Busy with EV chargers and patio lighting."),
    6: ("EV chargers and hot tubs all month.", "Summer projects in full swing."),
    7: ("Busy July, lots of AC-related circuit work.", "Heat wave brought in breaker trips."),
    8: ("Steady August.", "Vacations slowed things a little."),
    9: ("Back-to-school month, EV quotes up again.", "September steady."),
    10: ("Generator inlet season, people prepping for storms.", "Lots of generator questions."),
    11: ("Generators and early storm calls.", "First windstorm of the year."),
    12: ("Holiday lighting and storm outages.", "December storms, very busy."),
}
OPERATIONS_NOTES = ("Supplier raised wire prices again.", "Truck two was in the shop for a week.",
                    "Hired a new apprentice.", "Permit delays at the county.",
                    "Raised service-call fee slightly.")


def job_notes(history: CompanyHistory, randomness: random.Random) -> dict[str, tuple[str, ...]]:
    """The notes typed on each job, by job id."""
    return {job.job_id: _notes_for_job(job, randomness) for job in history.jobs}


def owner_notes(history: CompanyHistory, randomness: random.Random) -> dict[date, str]:
    """The owner's Markdown note for each month."""
    completed_by_month = Counter()
    services_by_month: dict[date, Counter] = {}
    for job in history.jobs:
        if job.lead.outcome is LeadOutcome.COMPLETED:
            month = job.completed_at.date().replace(day=1)
            completed_by_month[month] += 1
            services_by_month.setdefault(month, Counter())[job.lead.service.name] += 1

    notes = {}
    for month in simulated_months():
        top_service = services_by_month.get(month, Counter({"nothing much": 0})).most_common(1)[0][0]
        paragraphs = [
            f"{completed_by_month[month]} jobs done, mostly {top_service.lower()}.",
            randomness.choice(SEASONAL_NOTES[month.month]),
            *_story_notes(month),
        ]
        if randomness.random() < SHARE_OF_MONTHS_WITH_AN_OPERATIONS_NOTE:
            paragraphs.append(randomness.choice(OPERATIONS_NOTES))
        notes[month] = f"# {month:%B %Y}\n\n" + "\n\n".join(paragraphs) + "\n"
    return notes


def _notes_for_job(job: Job, randomness: random.Random) -> tuple[str, ...]:
    lead = job.lead
    story = city_story_in_effect(lead.customer.service_area.city, lead.created_at.date())

    if lead.outcome is LeadOutcome.CANCELED:
        return (randomness.choice(CANCELED_NOTES),) if randomness.random() < SHARE_OF_CANCELED_JOBS_WITH_A_NOTE else ()
    if lead.outcome is LeadOutcome.ESTIMATE_ONLY:
        if story.estimate_only_multiplier > 1 and randomness.random() < 0.6:
            return (randomness.choice(COMPETITOR_DECLINED_NOTES),)
        return (randomness.choice(ESTIMATE_DECLINED_NOTES),)
    if story.ticket_price_multiplier < 1 and randomness.random() < 0.5:
        return (randomness.choice(SMALL_JOB_NOTES),)
    if randomness.random() < SHARE_OF_COMPLETED_JOBS_WITH_A_NOTE:
        return (randomness.choice(WORK_NOTES[lead.service.name]),)
    return ()


def _story_notes(month: date) -> list[str]:
    """What the owner wrote about the planted stories, in the month they noticed."""
    notes = [story.owner_note for story in CITY_STORIES if add_months(story.starts, 1) == month]
    if month == AI_CALL_TAKER_ADOPTED_ON.replace(day=1):
        notes.append("Turned on Housecall Pro's AI call taker so calls stop going to voicemail "
                     "while I'm on a job.")
    if month == add_months(AI_CALL_TAKER_ADOPTED_ON.replace(day=1), 2):
        notes.append("The AI call taker is catching a lot of calls I used to miss.")
    if month == SOUTH_SOUND.opened_month:
        notes.append("Opened the South Sound location this month, with its own 253 number.")
    if month == CHATGPT_NOTICED_ON:
        notes.append("A couple of customers said they asked ChatGPT for an electrician and it "
                     "recommended us. Never had that before.")
    return notes
