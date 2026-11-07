# API

Interactive docs: <http://localhost:8000/docs> (OpenAPI). All routes are scoped to the caller's organization.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness + database check |
| GET | `/api/system/status` | Worker status, which integrations are configured, limits |
| GET | `/api/overview` | Dashboard data: stats, active/latest job, recent clips, projects, brand |
| GET / POST | `/api/brands` | List / create Brand Brain profiles |
| GET / PATCH / DELETE | `/api/brands/{id}` | Read / update / delete a brand |
| GET / POST | `/api/projects` | List (`?status=active|archived`) / create |
| GET / PATCH / DELETE | `/api/projects/{id}` | Read / update (incl. archive) / delete with its files |
| POST | `/api/projects/{id}/media` | Multipart upload (`file`); validated by content |
| GET | `/api/media` | Library of uploads (`?project_id=&kind=&q=`) |
| GET / DELETE | `/api/media/{id}` | Read / delete an original (and its productions' files) |
| POST | `/api/projects/{id}/jobs` | Start a production `{source_asset_id, topic, goal, platform, variations, brand_id}` |
| GET | `/api/jobs` | Production log (`?project_id=`) |
| GET | `/api/jobs/{id}` | Job with events, outputs, plan summary, trends, warnings |
| POST | `/api/jobs/{id}/retry` | Resume a failed/partial job (finished stages are kept) |
| POST | `/api/jobs/{id}/rerun` | Regenerate: new job, same footage and settings |
| GET | `/api/outputs` | Generated clips (`?project_id=&status=ready`) |
| PATCH | `/api/outputs/{id}` | Approve, edit title/caption/hashtags/CTA |
| GET | `/api/files/{key}?exp=&sig=[&dl=1]` | Signed, expiring private file access |

Errors return `{"detail": "human-readable message"}` with a meaningful status code
(400 bad input, 403 bad link, 404 not yours / not found, 413 too large, 415 wrong type, 422 unreadable media,
503 worker queue down).
