"""The notes a brief draws on: what people wrote about the cities in trouble,
and about the month itself."""

import calendar

from qdrant_client import QdrantClient

from app.analysis.months import add_months
from app.brief.facts import BriefFacts
from app.rag.note_index import NoteMatch, SearchFilters, search_notes

CITIES_TO_RESEARCH = 3
NOTES_PER_SEARCH = 3
# Causes start before their effects show up in a comparison, so notes reach back a full year.
NOTE_LOOKBACK_MONTHS = 12

# What to look for, given what the numbers proved fell.
QUESTION_FOR_FACTOR = {
    "demand": "fewer calls and new customers from {city}, people not finding us",
    "conversion": "customers in {city} turning down estimates, choosing a cheaper competitor",
    "ticket size": "smaller jobs in {city}, less work per visit",
}


def retrieve_notes(client: QdrantClient, facts: BriefFacts) -> list[NoteMatch]:
    month_ends = facts.month.replace(day=calendar.monthrange(facts.month.year, facts.month.month)[1])
    lookback_starts = add_months(facts.month, -(NOTE_LOOKBACK_MONTHS - 1))

    searches = [
        (QUESTION_FOR_FACTOR[factors[0]].format(city=city),
         SearchFilters(city=city, written_from=lookback_starts, written_until=month_ends))
        for city, factors in facts.struggling_cities[:CITIES_TO_RESEARCH]
    ]
    # The owner's notes are about the whole company, so they're searched without
    # the location filter that technicians' notes get.
    searches += [
        ("what changed in the business this month",
         SearchFilters(kind="owner_note", written_from=facts.month, written_until=month_ends)),
        ("what changed in the business this month",
         SearchFilters(kind="job_note", location=facts.location, written_from=facts.month, written_until=month_ends)),
    ]

    notes_by_id: dict[str, NoteMatch] = {}
    for question, filters in searches:
        for note in search_notes(client, question, filters, NOTES_PER_SEARCH):
            notes_by_id.setdefault(note.note_id, note)
    return list(notes_by_id.values())
