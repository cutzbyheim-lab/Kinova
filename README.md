# KINOVA

**Raw in. Remarkable out.** KINOVA is an AI content production and marketing automation platform.
Upload raw footage; KINOVA transcribes it, studies what's trending on YouTube for your topic, picks the
strongest moments, renders vertical clips with burned-in captions in your brand colors, checks them,
and writes the titles, captions and hashtags.

> **Milestone 1** — working app shell in the KINOVA design system, project & brand management,
> upload → trend-aware AI clips → review → download. Runs locally in single-user mode.

---

## Run it on Windows (first time, ~20 minutes)

### 1. Install Docker Desktop

1. Download **Docker Desktop for Windows** from <https://www.docker.com/products/docker-desktop/>.
2. Run the installer. Keep **"Use WSL 2 instead of Hyper-V"** ticked.
3. Restart your computer when it asks.
4. Open **Docker Desktop** from the Start menu and accept the terms. Wait until the bottom-left
   corner says **Engine running** (green).
   - If it says WSL needs updating, open **PowerShell** and run `wsl --update`, then reopen Docker Desktop.
5. In Docker Desktop → **Settings → Resources**, give it at least **4 GB memory** (6–8 GB is better for Whisper).

### 2. Get the code

Install **Git for Windows** (<https://git-scm.com/download/win>) if you don't have it, then in PowerShell:

```powershell
cd $HOME\Documents
git clone https://github.com/cutzbyheim-lab/Kinova.git
cd kinova
copy .env.example .env
notepad .env
```

### 3. Add your keys to `.env`

Everything works without keys — KINOVA just tells you clearly what it skipped. Add them when ready:

| Key | What it unlocks | Where to get it | Cost |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Claude picks the moments, plans each cut, writes copy | <https://platform.claude.com/> → API Keys | Pay per use; capped per production by `MAX_JOB_COST_USD` (default $0.50) |
| `YOUTUBE_API_KEY` | Trend research for your topic | Google Cloud Console → enable **YouTube Data API v3** → Credentials → API key | Free (10,000 units/day ≈ 99 productions) |
| `WHISPER_ENABLED` | Speech-to-text (captions, moment picking) | Already on — runs locally | Free |

Save the file.

### 4. Start KINOVA

```powershell
docker compose up --build
```

The first build downloads a few GB and takes 5–15 minutes. When you see `Uvicorn running` and
`celery@… ready`, open **<http://localhost:3000>**.

- Stop: press `Ctrl+C` (or `docker compose down`).
- Start again later: `docker compose up` (no `--build` needed unless the code changed).
- After editing `.env`: `docker compose up -d` to restart with the new keys.
- Update to the latest code: `git pull` then `docker compose up --build`.

> **First production note:** the first time Whisper runs it downloads its model (~150 MB for `base`).
> That production sits on "Transcribe" for a few minutes. Later ones start immediately.

### Troubleshooting

| Problem | Fix |
|---|---|
| `docker: command not found` / engine not running | Open Docker Desktop and wait for **Engine running**. |
| Port 3000 or 8000 already in use | Close the other app, or change `"3000:80"` in `docker-compose.yml` to e.g. `"3100:80"`. |
| A production is stuck on Transcribe | First run downloads the model — wait. Check `docker compose logs worker`. |
| "Worker offline" in the sidebar | `docker compose logs worker` — usually not enough memory; raise it in Docker Desktop settings. |
| Upload rejected | Must be MP4/MOV/WEBM/MKV, ≤ 15 min and ≤ 1 GB (change `MAX_VIDEO_SECONDS` / `MAX_UPLOAD_MB`). |

---

## How it works

```
Upload ─► Ingest ─► Transcribe ─► Trends ─► Moments ─► Render ─► Quality check ─► Copy ─► Library
          ffprobe    Whisper       YouTube    Claude      FFmpeg     ffprobe checks   Claude
          audio      (local)       Data API   Sonnet      9:16 +     size, length,    Haiku
                                              → JSON plan captions   audio, A/V sync
```

- **The AI never writes FFmpeg commands.** Claude returns a JSON editing plan; it is validated and clamped to the
  real footage, then executed by a deterministic renderer.
- **Nothing pretends.** Missing keys, skipped stages and fallbacks are shown in the Studio. Without Claude, a clearly
  labelled *non-AI heuristic* picks the cuts so you can still review the pipeline.
- **Costs are capped.** Each Claude call is estimated first; a production never goes over `MAX_JOB_COST_USD`.
  Every call is logged with real token usage (`ai_generations` table).
- **Resumable.** Each stage records its output. Retrying a failed job resumes where it stopped — no re-paying for
  finished work.
- **Originals are never touched.** Source uploads, derived files (audio, transcripts) and generated clips live in
  separate storage areas; private files are served only through expiring signed links.

## Project layout

```
kinova/
  apps/
    api/                 FastAPI backend + Celery worker (one codebase, two processes)
      app/
        api/             REST routes
        core/            config, database, tenant context, signing, logging
        models/          SQLAlchemy models (org-scoped)
        schemas/         Pydantic request/response models
        ai/              Claude provider + cost caps, planner, copywriter, Whisper, YouTube trends
        media/           ffprobe/ffmpeg wrappers, edit plan, captions, renderer, QC
        services/        storage, audit log
        workers/         Celery app, pipeline stages
      alembic/           database migrations
      tests/             pytest suite
    web/                 React + TypeScript + Vite + Tailwind
      src/
        components/      design-system pieces, layout, pipeline bar
        pages/           Overview, Studio, Job view, Library, Brand Brain, Settings…
        lib/             API client, types, formatting
  docs/                  architecture, database, API
  docker-compose.yml
```

The worker lives inside the API package (a *modular monolith*) so both processes share models and services.

## Developing without Docker

Requirements: Python 3.12+, Node 22+, PostgreSQL 16, Redis 7, FFmpeg.

```bash
# backend
cd apps/api
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
celery -A app.workers.celery_app worker -Q production --concurrency=1 --loglevel=INFO   # 2nd terminal

# frontend (3rd terminal)
cd apps/web
npm install
npm run dev        # http://localhost:5173, proxies /api to :8000

# tests (needs a kinova_test database)
cd apps/api && pytest
```

## Roadmap

| Milestone | Scope |
|---|---|
| **1 (this)** | Foundation, design system, Overview, Studio, Library, Brand Brain, trend-aware clip pipeline |
| 2 | Real accounts & login, teams, agency client workspaces, permissions |
| 3 | Campaigns & calendar, AI assistant that starts productions |
| 4 | Social publishing (official TikTok / Instagram / YouTube APIs), analytics from connected accounts |
| 5 | Plans, credits & billing, S3 storage, production deployment |

See [`docs/`](docs/) for architecture, database and API details.
