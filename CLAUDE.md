# CLAUDE.md

Local Business Intelligence Engine: project that lands raw data
from a fictional two-location electrical contractor (Housecall Pro CRM,
Grasshopper call logs, website form leads, Google Search Console) in
Postgres, attributes calls and leads to customers, and turns the numbers
into a plain-English monthly brief with RAG + OpenAI.

## Coding guidelines

- **Beautifully simple.** Modular and SOLID, but never over-abstracted:
  excessive modularity is not simple. Choose the simplest structure that
  fits the size of the problem, and refactor when it grows.
- **Readability first.** Long, descriptive names are welcome when they aid
  understanding (`share_of_location_customers`, `_caller_hung_up_while_ringing`).
  Don't trade readability for cleverness; if a line needs decoding, rewrite it.
- **One responsibility per module, class, and function.** Data (config,
  constants) is kept apart from logic.
- **A class only when it holds state; otherwise plain functions.** Public
  surface stays small; internals get a leading underscore.
- **Pass dependencies in** (e.g. a seeded `random.Random`), never globals.
- **Immutable data:** `@dataclass(frozen=True)`, tuples, `StrEnum` for fixed
  vocabularies. Keyword arguments for booleans, never a bare `True`, and for
  constructing objects with several fields of the same type.
- **Top-down reading order:** the main function tells the story; small,
  well-named helpers sit below it.
- **No speculative code:** no layers, options, or indexes "just in case".
- **Comments explain why**, especially when deviating from the obvious tool.
- Match the density and idiom of the surrounding code.

## Layout

```
generator/          synthetic data generator (python -m synthetic_data)
  synthetic_data/
    calibration.py      the business in numbers, incl. planted city stories (data only)
    customers.py, jobs.py   the truth: what really happened
    sources/            each system's imperfect view of the truth, incl. notes
apps/api/           FastAPI service
  migrations/         numbered .sql files (the schema)
  app/
    ingestion/          files -> raw tables, Grasshopper parsing, export coverage
    clean_layer/        raw -> clean, rebuilt from sql/*.sql in one transaction
    analysis/           hot services, city diagnosis, channel funnel, call handling
    rag/                OpenAI embeddings and the Qdrant note index
    brief/              facts -> notes -> drafted brief -> number guard -> template fallback
    routers/            the HTTP endpoints
apps/web/           vanilla-JS dashboard behind nginx (no build step)
evaluation/         grades the pipeline against the answer key; planted-story checks
docs/               README images
data/               generated files, git-ignored
  raw/                what the pipeline ingests
  answer_key/         hidden truth, used only to grade the pipeline
```

## Commands

```bash
# Generate data (deterministic: same seed, byte-identical output)
cd generator && python -m synthetic_data

# Start services; Postgres is on host port 5434 (5432 inside Docker)
docker compose up -d postgres qdrant

# Apply pending migrations
docker compose run --rm --no-deps api python -m app.migrations

# Load data/raw into the raw tables (safe to re-run: stored files are skipped)
docker compose run --rm --no-deps api python -m app.ingestion

# Rebuild the clean layer from raw (about 20 s)
docker compose run --rm --no-deps api python -m app.clean_layer

# Sync the note index in Qdrant (needs OPENAI_API_KEY; embeds only new or edited notes)
docker compose run --rm --no-deps api python -m app.rag

# Dashboard on :8080, API on :8000
docker compose up -d api web

# Tests (run in apps/api and in evaluation)
python -m pytest

# Grade the clean layer against data/answer_key
cd evaluation && python -m grading

# Generate a seed, run the whole pipeline into its own database, grade it
evaluation/evaluate_seed.sh 7    # PYTHON=.venv/Scripts/python on Windows
```

On Windows Git Bash, Docker commands that pass container paths need
`MSYS_NO_PATHCONV=1`, or `/data/...` is rewritten to a Windows path.

## Database

Five schemas, in the order data flows:
- `raw`: every file exactly as received (JSON, CSV rows, text), never updated.
  A file's SHA-256 makes loading idempotent.
- `staging`: views that unpack raw files into one row per record, keeping
  each record's latest version.
- `clean`: typed, normalized, deduplicated, attributed tables, emptied and
  rebuilt from staging by `app/clean_layer/sql/*.sql`. Includes `calls`
  (legs reassembled and classified), `leads` (web and phone, with channel
  and evidence), and `notes`.
- `analytics`: views of business-ready numbers built on clean.
- `reference`: business facts no source records (zip code → location,
  internal phone numbers, office lead sources, service keywords). Edit these
  to point the pipeline at another business.

Clean-layer conventions:
- Phone numbers are E.164 (`+14255550142`), or NULL.
- Timestamps are `TIMESTAMPTZ`, whatever the source format.
- Money is `BIGINT` cents, never floats.
- Empty strings become NULL.
- Duplicates and spam are flagged, not deleted.
- Location is inferred from the zip code; Housecall Pro doesn't record it.

## Rules

- Schema changes go in a **new** numbered migration; never edit one that
  has already run. Plain `CREATE`, no `IF NOT EXISTS`.
- Plain SQL with bound parameters; no ORM models, never string-built SQL.
- The pipeline (`apps/`) must never import from `generator/` or read
  `data/answer_key/`. It would be grading its own exam. `evaluation/` may
  import the pipeline to test it; never the other way around.
- An analysis names a change as a reason only when it's beyond chance
  (about two standard errors), and flags small samples and biased rates
  rather than hiding them.
- The brief's model may only copy numbers from the facts and notes it's
  given; facts are formatted once, in code, and named so they can't be
  misread. Every number is checked by the guard.
- Text from the API, especially the model's, is untrusted: the dashboard
  inserts it only through the escaping `html` template.
- Synthetic data uses only reserved fictional values: 555 phone numbers,
  `example.com/.net/.org` emails, the `.example` domain, RFC 5737 IP addresses.
- Never commit real exports, client data, or anything under `data/`.
