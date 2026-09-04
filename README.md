# SubLynt

SubLynt is a complete, local-first subtitle analysis, repair, and conversion application. Upload an SRT or WebVTT file, inspect timing and readability findings, choose conservative or advanced repairs, compare the original with the result, and download a round-trip-validated subtitle file.

No AI service, account, external dataset, or paid API is involved. Uploaded text is never executed or logged.

## Interface

The responsive four-step interface includes:

1. A keyboard-accessible drag-and-drop upload with progress and clear format constraints.
2. Summary cards for format, cue count, timeline duration, average duration, reading speed, and issue count, plus a severity-filtered findings table.
3. A recommended safe-repair preset, opt-in timing/text operations, output-format selection, and configurable analysis thresholds.
4. Side-by-side original/corrected cues, changed-cue filtering, an audit log, final validation status, download, and idempotent deletion.

Severity is always represented by a symbol and text as well as color. Focus states, labels, live status, semantic tables, and reduced-motion support are included.

## Architecture

The project is a small monorepo:

```text
backend/
  app/                  FastAPI routes, configuration, persistence, job service
  sublynt_core/         framework-independent parser/analyzer/transformer
  alembic/              database migration
  tests/                unit, security, and complete API workflow tests
frontend/
  src/                  React + TypeScript single-page workflow
  tests/                validation, formatting, and results-rendering tests
docs/architecture.md    processing algorithms and layer boundaries
docker-compose.yml      production-style local stack
```

Only metadata and the change log are stored in SQLAlchemy. Source and generated subtitles use opaque UUID filenames under a dedicated data directory. SQLite is the default; models and queries remain PostgreSQL-compatible. Read [the architecture note](docs/architecture.md) for processing order, split/merge algorithms, trade-offs, and lifecycle details.

## Quick start with Docker

Requirements: Docker with Compose.

```bash
cp .env.example .env
docker compose up --build
```

Open <http://localhost:3000>. The API documentation is reachable through the backend container at `/docs`; for direct host access in development, use the local setup below.

If port 3000 is occupied, set `SUBLYNT_PORT` in `.env` (for example, `SUBLYNT_PORT=3100`) and open that port instead.

The Compose startup applies Alembic migrations, waits for backend health, and serves the built frontend from nginx. Persistent metadata and subtitle files live in the `sublynt-data` Docker volume.

Stop the stack with `docker compose down`. Add `-v` only if you intentionally want to delete all persisted SubLynt data.

## Local development

Requirements: Python 3.12+, Node 22+, and npm.

Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
mkdir -p data/files
alembic upgrade head
uvicorn app.main:app --reload
```

Frontend, in another terminal:

```bash
cd frontend
npm install
npm run dev
```

For local Vite development, its proxy expects the backend at `http://localhost:8000`. Alternatively, set `VITE_API_URL=http://localhost:8000/api/v1` when building. Open <http://localhost:5173>; OpenAPI is at <http://localhost:8000/docs>.

## Configuration

Backend settings are environment variables prefixed by `SUBLYNT_`:

| Variable | Default | Purpose |
| --- | --- | --- |
| `SUBLYNT_ENVIRONMENT` | `development` | Deployment label |
| `SUBLYNT_DATABASE_URL` | `sqlite:///./data/sublynt.db` | SQLAlchemy database URL |
| `SUBLYNT_DATA_DIR` | `./data/files` | Dedicated subtitle artifact directory |
| `SUBLYNT_MAX_UPLOAD_BYTES` | `5242880` | Maximum upload size (5 MB) |
| `SUBLYNT_RETENTION_HOURS` | `24` | Age after which cleanup deletes jobs |
| `SUBLYNT_CORS_ORIGINS` | local ports | Comma-separated allowed browser origins |
| `SUBLYNT_PORT` | `3000` | Docker frontend host port (Compose only) |
| `SUBLYNT_API_PORT` | `8000` | Docker API host port (Compose only) |

`VITE_API_URL` optionally sets the browser API root at frontend build time. The default, `/api/v1`, works through nginx and Compose.

Run retention cleanup manually or from a scheduler:

```bash
cd backend
sublynt-cleanup
```

Cleanup runs during API startup and is checked hourly while the API is running.

## API example

```bash
# Upload and analyze
curl -F 'file=@captions.srt' http://localhost:8000/api/v1/files

# Apply conservative repairs and convert; replace FILE_ID
curl -X POST http://localhost:8000/api/v1/files/FILE_ID/transform \
  -H 'Content-Type: application/json' \
  -d '{"preset":"safe","output_format":"vtt"}'

# Preview, download, then delete
curl http://localhost:8000/api/v1/files/FILE_ID/preview
curl -OJ http://localhost:8000/api/v1/files/FILE_ID/download
curl -X DELETE http://localhost:8000/api/v1/files/FILE_ID
```

Errors consistently use `{ "error": { "code": "...", "message": "..." } }`. The DELETE endpoint is idempotent.

## Analysis and transformation behavior

Analysis detects malformed or missing timestamps, negative timing syntax, end-before-start timing, empty cues, duplicate identifiers, out-of-order cues, overlaps, insufficient gaps, short/long durations, excessive CPS/WPM, long lines, excessive lines, consecutive duplicate text, malformed SRT numbering, and malformed VTT headers. Every issue has a stable code, severity, cue reference, relevant timestamp, explanation, and repair availability.

The default thresholds are 1–7 seconds duration, an 80 ms minimum gap, 20 characters/second, 180 words/minute, 42 characters/line, and two lines/cue. They are adjustable in the UI and API.

Safe repair sorts cues, renumbers them, removes empty cues, and replaces end-before-start timing with the configured minimum duration. It does not alter caption text or otherwise shift valid timing. Explicit options can shift timestamps without allowing negative results, scale for playback speed, remove exact duplicates, enforce gaps and durations, resolve overlaps, split long text, or merge compatible short neighbors. Transformations run in a fixed order and return old/new values for each change. Output conversion is supported both ways.

Splitting prefers sentence boundaries, then punctuation, then words; only an unbroken token longer than the capacity is hard-split. Time is divided proportionally by character count while reserving minimum duration when source timing permits. Merging only considers adjacent short cues and enforces gap, duration, line-capacity, CPS, and WPM limits. See [docs/architecture.md](docs/architecture.md) for exact details.

## Security

- Uploads are size-bounded and strictly decoded as UTF-8 (BOM accepted); NUL-containing/binary and unsupported files are rejected.
- Uploaded names are display data only. UUIDs identify jobs and artifacts, and every stored path is containment-checked.
- Text is returned as JSON and rendered by React text nodes, never as HTML.
- Generated downloads use sanitized filenames and are reparsed before publication.
- CORS is explicit, nginx sets a restrictive content policy and security headers, internal exceptions/paths are not returned, and logs contain metadata only.
- There is no archive handling, content execution, remote fetch, or user-controlled path construction.

For internet-facing deployment, put the service behind a trusted reverse proxy with TLS, request timeouts, body limits, and rate limiting. Application-level rate limiting is intentionally omitted because correct enforcement belongs in the shared ingress when the API is horizontally scaled.

## Verification

```bash
cd backend
ruff check .
ruff format --check .
mypy app sublynt_core
pytest --cov=app --cov=sublynt_core

cd ../frontend
npm run lint
npm test
npm run build

cd ..
docker compose config
docker compose up --build
```

Backend tests cover timestamp conversion, parsing/serialization, BOM and line endings, multiline cues, malformed input, overlaps/gaps, speed metrics, negative shifts, playback scaling, sorting, numbering, duration repairs, splitting, merging, conversion, round trips, filename/path safety, oversized/binary input, literal HTML-like text, and the full API lifecycle.

## Current limitations and future work

- SubLynt is intentionally a subtitle-file utility, not a waveform/video editor or language tool.
- WebVTT `NOTE`, `STYLE`, and `REGION` blocks are safely ignored rather than preserved. Cue identifiers and common settings are preserved.
- Malformed cue blocks are reported when valid cues remain, but byte-perfect preservation is not a goal; serialization normalizes whitespace and line endings.
- The MVP processes jobs synchronously. The `JobService` and framework-independent core form a clean boundary for a future worker queue.
- PostgreSQL schema compatibility is maintained, but production connection pooling and a PostgreSQL Compose profile are future operational work.
- Future improvements could include batch upload, richer line reflow, downloadable JSON reports, and visual regression snapshots.
