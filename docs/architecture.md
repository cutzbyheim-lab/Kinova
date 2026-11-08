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
| plan | contact sheets (frames every ≥2 s, labelled `S<source> HH:MM:SS`) + word-timed transcripts → Claude Sonnet → JSON `EditPlan` (clips with `focus_x`/`zoom`, B-roll slots, music, hook, CTA); validated, one repair attempt | non-AI heuristic, labelled |
| assets | search + download Pexels portrait clips for each B-roll slot (cached per org), resolve music tracks | skipped / warning, cut renders without them |
| render | per-clip segments (subject-centred crop + punch-in) → lossless concat → music ducking + loudness → **Remotion motion layer** (`apps/api/motion`: captions, hook, B-roll entrances, CTA) → FFmpeg finish (grade, grain, vignette, SFX) | motion fails → FFmpeg look (ASS captions, hard B-roll); then retry without extras |
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

## Motion layer

`apps/api/motion` is a Remotion project built to the rules in `.claude/skills/remotion-motion-graphics`
(springs, staggered entrances, faster exits, one hero color per frame, theme file). The Docker build bundles it and
downloads Remotion's headless Chrome. The worker calls `node render.mjs` with a props file; assets are served to
Chrome from a private `127.0.0.1` port for the length of the render, and the output is video-only — the mixed audio is
muxed back in the finish pass. Hook-end and CTA-start times are computed once in Python (`render.timings`) so the
sound effects land on the same frames as the animation.
