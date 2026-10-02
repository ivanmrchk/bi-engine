"""Drafts the brief with an OpenAI model, from the facts and the notes only."""

import json

from openai import OpenAI
from pydantic.dataclasses import dataclass

from app.config import settings
from app.rag.note_index import NoteMatch

SYSTEM_PROMPT = """\
You write a short monthly brief for the owner of a two-location electrical
contracting business. The owner is busy and not a data person: write in
plain English, like a sharp operations manager would.

You get two things:
- FACTS: numbers from the company's own data, already calculated.
- NOTES: what technicians and the owner wrote down.

Rules:
- FACTS are proven. "factors_that_clearly_fell" lists what declined beyond
  chance: demand (fewer people asking), conversion (fewer saying yes), or
  ticket size (smaller jobs). A factor listed there FELL, even if revenue
  rose overall. "factor_changes" shows each factor's change.
- NOTES are anecdotes. Use them to illustrate or explain FACTS, never to
  contradict or replace them. If a note doesn't fit the facts, leave it out.
- Use only numbers that appear in FACTS or NOTES, copied exactly as written.
  Never calculate, round, add, or compare numbers into new ones.
- Prefer words to numbers where you can ("about half", "most").
- A fact marked "too few jobs to compare" or "unreliable" is not evidence;
  don't build conclusions on it.
- Connect the numbers with the notes when they explain each other, and say
  when something is the notes' explanation rather than a proven cause.
- If a city has a clear problem, name the factor that fell, in plain words.
- Skip filler: every sentence should help the owner decide something.

Write:
- headline: one sentence, the single most important thing this month.
- summary: 2-3 sentences on how the month went.
- biggest_opportunity: 1-2 sentences, the best thing to lean into.
- biggest_risk: 1-2 sentences, the thing most worth fixing, and a first step.
"""

BRIEF_SCHEMA = {
    "name": "monthly_brief",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "headline": {"type": "string"},
            "summary": {"type": "string"},
            "biggest_opportunity": {"type": "string"},
            "biggest_risk": {"type": "string"},
        },
        "required": ["headline", "summary", "biggest_opportunity", "biggest_risk"],
        "additionalProperties": False,
    },
}


@dataclass(frozen=True)
class BriefText:
    headline: str
    summary: str
    biggest_opportunity: str
    biggest_risk: str

    def as_text(self) -> str:
        return "\n".join((self.headline, self.summary, self.biggest_opportunity, self.biggest_risk))


def source_material(sheet: dict, notes: list[NoteMatch]) -> str:
    """Everything the model is given, as one JSON document; the guard checks against the same text."""
    return json.dumps(
        {
            "FACTS": sheet,
            "NOTES": [
                {
                    "written_on": note.written_on.isoformat(),
                    "city": note.city,
                    "text": note.body,
                    "times_written": note.times_written,
                }
                for note in notes
            ],
        },
        indent=2,
    )


def draft_brief(material: str, invented_numbers_last_time: list[str] | None = None) -> BriefText:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": material},
    ]
    if invented_numbers_last_time:
        messages.append({
            "role": "user",
            "content": (
                f"Your last draft used numbers that are not in FACTS or NOTES: "
                f"{', '.join(invented_numbers_last_time)}. Rewrite it using only numbers given above."
            ),
        })

    response = OpenAI(api_key=settings.openai_api_key).chat.completions.create(
        model=settings.brief_model,
        messages=messages,
        response_format={"type": "json_schema", "json_schema": BRIEF_SCHEMA},
    )
    return BriefText(**json.loads(response.choices[0].message.content))
