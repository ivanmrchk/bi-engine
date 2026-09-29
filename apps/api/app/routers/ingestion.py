"""Getting data in: owner uploads of Grasshopper exports, and full pipeline runs.

The endpoints are plain `def`, not `async def`: storing and rebuilding
block on the database for seconds, and FastAPI runs plain functions in a
worker thread so they don't stall every other request meanwhile.
"""

from dataclasses import dataclass

from fastapi import APIRouter, HTTPException, UploadFile

from app.clean_layer.rebuild import clean_table_row_counts, rebuild_clean_layer
from app.config import settings
from app.db import engine
from app.ingestion.coverage import CallCoverage, call_coverage
from app.ingestion.feeds import GRASSHOPPER_CALLS
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
