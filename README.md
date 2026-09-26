# Local Business Intelligence Engine

A portfolio project demonstrating an end-to-end pattern from real client work:
land raw data from multiple sources (Housecall Pro CRM, Grasshopper call
logs, website form leads, Google Search Console) into Postgres, analyze it for
business signal ("what's hot, what's lagging"), and layer retrieval-augmented
generation on top to turn the numbers into a plain-English brief.

Built with synthetic, multi-location data — see [`generator/`](generator/README.md).
No real client data or branding is used anywhere in this repo.

## Architecture

Two separate services, deployed as two separate Fly.io apps:

- **`apps/api`** — FastAPI service. Owns Postgres (event storage, JSONB
  payloads on a single `events` table — the "dump as JSON, query on a needs
  basis" pattern) and Qdrant (vector search / RAG over free-text notes).
  Publicly reachable so its auto-generated `/docs` (Swagger UI) works as a
  live, explorable demo.
- **`apps/web`** — a small static dashboard (vanilla JS, no build step)
  served by nginx. nginx reverse-proxies `/api/*` to the API service, so the
  browser only ever talks to the web app's own origin. Locally that proxy
  target is the `api` docker-compose service; in production it's the API
  app's Fly private-network hostname (`bi-engine-api.internal:8000`) — same
  proxy config, one env var different. This also means the browser never
  needs to know about, or CORS against, the API's public URL directly.

```
apps/api/   FastAPI + SQLAlchemy + Qdrant client
apps/web/   static dashboard + nginx reverse proxy
```

## Run it locally

```bash
cp .env.example .env        # add OPENAI_API_KEY if you have one; optional
docker compose up --build
```

- API: http://localhost:8000/docs
- Dashboard: http://localhost:8080

Generate the synthetic raw data (written to `data/`, which is git-ignored):

```bash
cd generator
pip install -r requirements.txt
python -m synthetic_data
```

Loading that data into the API is the ingestion layer, currently in progress.

## Deploy to Fly.io

Two apps in the same Fly org so they can reach each other over the private
network:

```bash
cd apps/api
fly launch --no-deploy --name bi-engine-api        # first time only
fly secrets set OPENAI_API_KEY=... QDRANT_URL=... QDRANT_API_KEY=... DATABASE_URL=...
fly deploy

cd ../web
fly launch --no-deploy --name bi-engine-web         # first time only
fly deploy
```

`apps/web/fly.toml` already points `API_UPSTREAM` at
`bi-engine-api.internal:8000` — Fly wires that hostname up automatically
over WireGuard between any two apps in the same org, no extra networking
setup required.

## Status

Tracked in the portfolio build tracker. Rough order: ingestion + analysis
endpoints first, then the RAG layer, then the LLM brief generator, then
deploy both apps and wire up the custom domain.
