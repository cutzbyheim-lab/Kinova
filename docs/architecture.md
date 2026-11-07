# Architecture

## Shape

A **modular monolith**: one Python codebase runs as two processes — the FastAPI web API and a Celery
worker — sharing models and services. A React single-page app talks to the API over REST.

```
Browser ──HTTP──► nginx (web) ──/api──► FastAPI ──► PostgreSQL
                                          │   ▲
                                   enqueue│   │status / outputs
                                          ▼   │
                                        Redis ──► Celery worker ──► FFmpeg, Whisper
                                                       │
                                                       ├──► Claude API (planning, copy)
                                                       └──► YouTube Data API (trends)
                         private storage volume (shared by API and worker)
```

Heavy work never runs in a request. Uploads are validated in the request (ffprobe is sub-second);
everything else happens in the worker, one job at a time (`--concurrency=1`) because video work is
CPU-bound on a laptop.

## Production pipeline

`app/workers/pipeline.py` runs eight stages. Each stage writes into `production_jobs.result` and marks
`<stage>_done`, so a retried job resumes without repeating finished work.

| Stage | What happens | If unavailable |
|---|---|---|
| ingest | probe source, extract 16 kHz mono audio | fatal: unreadable file |
| transcribe | faster-whisper (CPU, int8), word timestamps | skipped → cuts without speech |
| trends | YouTube search (top viewed, last 30 days) + video details → pattern summary | skipped → plan without trends |
| plan | Claude Sonnet → JSON `EditPlan`; validated, one repair attempt | non-AI heuristic, labelled |
| render | per-clip segments → lossless concat → captions (ASS/libass) + loudness | retry without captions |
| qc | dimensions, duration, audio, A/V drift, caption cues | re-render once, else mark failed |
| copy | Claude Haiku → title, hook, caption, hashtags, CTA | skipped, working titles kept |
| deliver | final status: succeeded / partial / failed | — |

### Why the renderer cuts segments first

A single filtergraph that trims the same input many times makes FFmpeg buffer decoded frames between
clips and can exhaust memory on long footage (it was OOM-killed at 8 GB on a 48 s test). Cutting each
clip with input seeking keeps peak memory under ~400 MB regardless of source length.

### Editing plans are data, not commands

`app/media/plan.py` defines the contract (`EditPlan → Variation → Clip`). `validate_plan` clamps clips
to the source, drops sub-0.8 s fragments, trims cuts over 90 s, dedupes keys, and rejects plans with
nothing renderable. The renderer only ever sees validated plans.

## AI providers

- `app/ai/llm.py` — `ClaudeLLM.complete()` is the single entry point. It estimates cost before each call
  and raises `BudgetExceeded` instead of calling if the job cap would be passed; actual usage is recorded
  to `ai_generations` and added to `production_jobs.cost_usd`.
- `app/ai/transcription.py` — `Transcriber` protocol; `LocalWhisper` today.
- `app/ai/trends.py` — `fetch_trending` (network) and `summarize` (pure) are separate for testing.

Swapping a provider means implementing the same small interface.

## Multi-tenancy & security

- Every tenant-owned table has `org_id`; routes load rows with `get_owned(db, Model, id, ctx)` which
  filters by the caller's organization and returns 404 otherwise.
- `RequestContext` (user, org, role) is produced by `get_ctx`. Milestone 1 returns a local single user;
  real authentication replaces only that function.
- Media is stored privately; the browser receives HMAC-signed links that expire (default 1 h).
- API keys live only in server environment variables.
- Uploads are validated by extension *and* by probing the content; filenames are sanitised; storage
  keys are resolved inside the storage root only.
- Mutating actions write `audit_logs`.
- Customer media is never sent to Claude: only transcripts, trend summaries and brand text are.

## Frontend

React 19 + TypeScript (strict) + Vite + Tailwind v4, TanStack Query for server state (polling while a
job runs), React Router. Design tokens live in `src/styles.css` (`@theme`). Pages that aren't built yet
are honest "in production" pages — no fake data.
