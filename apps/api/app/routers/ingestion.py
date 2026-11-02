"""Getting data in: owner uploads of Grasshopper exports, relay-engine's
feed uploads, and full pipeline runs.

The endpoints are plain `def`, not `async def`: storing and rebuilding
block on the database for seconds, and FastAPI runs plain functions in a
worker thread so they don't stall every other request meanwhile.

/{feed_name} is a catch-all path, so it's registered last: a path like
/run or /coverage must match its own literal route first, or this one
would swallow it.

relay-engine's uploads carry real customer data, so they need the shared
key in X-Relay-Ingest-Key. The owner's Grasshopper upload stays open: the
dashboard has no secret it could keep.
"""

import secrets
from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, UploadFile

from app.clean_layer.rebuild import clean_table_row_counts, rebuild_clean_layer
from app.config import settings
from app.db import engine
from app.ingestion.coverage import CallCoverage, call_coverage
from app.ingestion.feeds import Feed, GRASSHOPPER_CALLS, feed_by_name
from app.ingestion.grasshopper_report import NotAGrasshopperReport
from app.ingestion.raw_directory import FeedLoadResult, load_raw_directory
from app.ingestion.raw_store import store_file

router = APIRouter()


@dataclass(frozen=True)
class GrasshopperUploadResult:
    file_name: str
    was_new: bool
    coverage: CallCoverage


@dataclass(frozen=True)
class PipelineRunResult:
    feeds: list[FeedLoadResult]
    clean_table_rows: dict[str, int]
    coverage: CallCoverage


@dataclass(frozen=True)
class FeedUploadResult:
    feed: str
    file_name: str
    was_new: bool


@dataclass(frozen=True)
class RebuildResult:
    clean_table_rows: dict[str, int]


@router.post("/grasshopper", response_model=GrasshopperUploadResult)
def upload_grasshopper_export(file: UploadFile) -> GrasshopperUploadResult:
    """Store one Grasshopper call-detail export and rebuild the clean layer.

    Uploading a file that's already stored changes nothing. The response
    lists any stretch of time no export covers, so it can be re-exported.
    """
    file_name = file.filename or "grasshopper_upload.csv"
    try:
        with engine.begin() as connection:  # the file and the rebuild succeed together, or not at all
            stored = store_file(connection, GRASSHOPPER_CALLS, file_name, file.file.read())
            if stored.was_new:
                rebuild_clean_layer(connection)
    except (NotAGrasshopperReport, UnicodeDecodeError) as error:
        raise HTTPException(status_code=422, detail=f"{file_name} is not a Grasshopper call-detail export: {error}")

    with engine.connect() as connection:
        return GrasshopperUploadResult(file_name, stored.was_new, call_coverage(connection))


@router.post("/run", response_model=PipelineRunResult)
def run_pipeline() -> PipelineRunResult:
    """Load every new file in the raw data folder, then rebuild the clean layer."""
    feeds = load_raw_directory(engine, settings.raw_data_dir)
    with engine.begin() as connection:
        rebuild_clean_layer(connection)
        return PipelineRunResult(feeds, clean_table_row_counts(connection), call_coverage(connection))


@router.get("/coverage", response_model=CallCoverage)
def get_call_coverage() -> CallCoverage:
    """Which stretches of time no Grasshopper export covers."""
    with engine.connect() as connection:
        return call_coverage(connection)


def _require_relay_ingest_key(x_relay_ingest_key: Annotated[str | None, Header()] = None) -> None:
    if not settings.relay_ingest_key:
        raise HTTPException(status_code=503, detail="relay uploads are turned off: RELAY_INGEST_KEY isn't set")
    # compare_digest takes as long for a near-miss as for a wild guess, so timing gives nothing away.
    if x_relay_ingest_key is None or not secrets.compare_digest(
        x_relay_ingest_key.encode(), settings.relay_ingest_key.encode()
    ):
        raise HTTPException(status_code=401, detail="missing or wrong X-Relay-Ingest-Key")


@router.post("/rebuild", response_model=RebuildResult, dependencies=[Depends(_require_relay_ingest_key)])
def rebuild_after_relay_pull() -> RebuildResult:
    """Rebuild the clean layer once, after relay-engine uploaded a pull's pages with rebuild=false."""
    with engine.begin() as connection:
        rebuild_clean_layer(connection)
        return RebuildResult(clean_table_row_counts(connection))


@router.post(
    "/{feed_name}", response_model=FeedUploadResult, dependencies=[Depends(_require_relay_ingest_key)]
)
def upload_feed_file(feed_name: str, file: UploadFile, rebuild: bool = True) -> FeedUploadResult:
    """Store one file for any feed except Grasshopper, which has its own endpoint above.

    This is relay-engine's (a separate repo) only way in: it fetches from
    Housecall Pro, the website lead form, and Search Console, and POSTs
    each page here as soon as it has it, one file at a time, instead of
    writing to the raw data directory directly. Uploading a file that's
    already stored for this feed changes nothing.

    A rebuild takes about 20 seconds, so rebuilding after every page would
    make a 30-page pull take ten minutes. A multi-page pull passes
    rebuild=false on each page and calls POST /ingest/rebuild once at the end.
    """
    feed = _feed_for_upload(feed_name)
    file_name = file.filename or f"{feed_name}.json"
    try:
        with engine.begin() as connection:  # the file and the rebuild succeed together, or not at all
            stored = store_file(connection, feed, file_name, file.file.read())
            if stored.was_new and rebuild:
                rebuild_clean_layer(connection)
    except UnicodeDecodeError as error:
        raise HTTPException(status_code=422, detail=f"{file_name} isn't valid text for the {feed_name} feed: {error}")

    return FeedUploadResult(feed.name, file_name, stored.was_new)


def _feed_for_upload(feed_name: str) -> Feed:
    feed = feed_by_name(feed_name)
    if feed is None:
        raise HTTPException(status_code=404, detail=f"no such feed: {feed_name}")
    if feed is GRASSHOPPER_CALLS:
        raise HTTPException(status_code=400, detail="grasshopper exports go through POST /ingest/grasshopper")
    return feed
