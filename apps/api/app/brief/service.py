"""Writes a month's brief: facts, then notes, then a draft the guard approves.

A draft that uses a number not found in its facts or notes is sent back
once with the offending numbers named. If the second draft still invents
numbers, or there's no OpenAI key, the plain template brief is used
instead. A brief never states a number the data doesn't support.
"""

from datetime import date

from pydantic.dataclasses import dataclass
from qdrant_client import QdrantClient
from sqlalchemy import Connection

from app.brief.context import retrieve_notes
from app.brief.facts import gather_facts
from app.brief.guard import invented_numbers
from app.brief.template import template_brief
from app.brief.writer import BriefText, draft_brief, source_material
from app.config import settings
from app.rag.embeddings import EmbeddingsUnavailable
from app.rag.note_index import NoteMatch

DRAFT_ATTEMPTS = 2


@dataclass(frozen=True)
class Brief:
    month: date
    location: str | None
    text: BriefText
    written_by: str  # the model's name, or "template"
    rejected_drafts: list[list[str]]  # the invented numbers in each rejected draft
    facts: dict
    notes: list[NoteMatch]


def write_brief(connection: Connection, client: QdrantClient, month: date, location: str | None = None) -> Brief:
    facts = gather_facts(connection, month, location)

    if not settings.openai_api_key:
        return Brief(month, location, template_brief(facts.sheet), "template", [], facts.sheet, [])

    try:
        notes = retrieve_notes(client, facts)
    except EmbeddingsUnavailable:
        notes = []
    material = source_material(facts.sheet, notes)

    rejected_drafts: list[list[str]] = []
    for _ in range(DRAFT_ATTEMPTS):
        draft = draft_brief(material, rejected_drafts[-1] if rejected_drafts else None)
        invented = invented_numbers(draft.as_text(), material)
        if not invented:
            return Brief(month, location, draft, settings.brief_model, rejected_drafts, facts.sheet, notes)
        rejected_drafts.append(invented)

    return Brief(month, location, template_brief(facts.sheet), "template", rejected_drafts, facts.sheet, notes)
