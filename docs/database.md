# Database

PostgreSQL 16, SQLAlchemy 2, migrations in `apps/api/alembic/versions`. All primary keys are UUIDs;
all tenant-owned tables carry an indexed `org_id` with `ON DELETE CASCADE` from `organizations`.

| Table | Purpose | Key columns |
|---|---|---|
| `organizations` | Tenant (creator, business or agency) | `slug` (unique), `plan`, `kind` |
| `users` | People | `email` (unique), `password_hash` (null in local mode) |
| `memberships` | User ↔ org with role | unique (`org_id`, `user_id`), `role` owner/admin/editor/viewer/client |
| `brands` | Brand Brain profiles | voice, audience, goals, editing_style, instructions, `colors` JSON |
| `projects` | Groups footage, jobs and clips | `topic` (trend research), `brand_id`, `status` |
| `media_assets` | Original uploads (never modified) | `storage_key`, `sha256`, duration/size, `has_audio` |
| `production_jobs` | One pipeline run | `status`, `stage`, `progress`, `settings` JSON, `result` JSON (per-stage outputs), `cost_usd`, `attempts` |
| `job_events` | Workflow history shown in the Studio | `stage`, `status`, `message` |
| `generated_assets` | Rendered clips | `variation_key`, `edit_plan` JSON, `qc` JSON, copy fields, `approved`, `version` |
| `ai_generations` | Every external AI call | `model`, `purpose`, tokens, `cost_usd`, `status` |
| `campaigns` | Campaign foundation (UI in a later milestone) | `goal`, `status`, dates |
| `audit_logs` | Who did what | `action`, `entity_type`, `entity_id`, `data` |

Planned for later milestones: `subscriptions`, `credit_ledger`, `social_connections`, `analytics_events`.

## Working with migrations

```bash
cd apps/api
alembic revision --autogenerate -m "describe change"   # after editing models
alembic upgrade head
```

The API container runs `alembic upgrade head` on start.
