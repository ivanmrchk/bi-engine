from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import init_db
from app.routers import analysis, brief, ingestion, rag


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Local Business Intelligence Engine", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingestion.router, prefix="/ingest", tags=["ingestion"])
app.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
app.include_router(rag.router, prefix="/rag", tags=["rag"])
app.include_router(brief.router, prefix="/brief", tags=["brief"])


@app.get("/health")
def health():
    return {"status": "ok"}
