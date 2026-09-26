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
  vocabularies. Keyword arguments for booleans, never a bare `True`.
- **Top-down reading order:** the main function tells the story; small,
  well-named helpers sit below it.
- **No speculative code:** no layers, options, or indexes "just in case".
- **Comments explain why**, especially when deviating from the obvious tool.
- Match the density and idiom of the surrounding code.

## Layout

```
generator/          synthetic data generator (python -m synthetic_data)
  synthetic_data/
    calibration.py      the business in numbers (data only)
    customers.py, jobs.py   the truth: what really happened
    sources/            each system's imperfect view of the truth
apps/api/           FastAPI service
  migrations/         numbered .sql files (the schema)
  app/                application code
apps/web/           static dashboard behind nginx
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
```

## Database

Three schemas:
- `raw`: every file exactly as received (JSONB), never updated. A file's
  SHA-256 makes loading idempotent.
- `reference`: business facts no source records (zip code → location,
  internal phone numbers). Edit these to point the pipeline at another business.
- `clean`: typed, normalized, deduplicated tables, always rebuildable from `raw`.

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
  `data/answer_key/`. It would be grading its own exam.
- Synthetic data uses only reserved fictional values: 555 phone numbers,
  `example.com/.net/.org` emails, the `.example` domain, RFC 5737 IP addresses.
- Never commit real exports, client data, or anything under `data/`.
