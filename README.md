# Dataset Request Desk

An internal platform for requesting, assigning, delivering, and reviewing robot teleoperation datasets. It combines a FastAPI/SQLAlchemy API, PostgreSQL, and a deliberately compact React interface.

## Run it

Prerequisite: Docker with Compose.

```bash
docker compose up --build
```

Then open [http://localhost:3000](http://localhost:3000). The API docs are at [http://localhost:8000/docs](http://localhost:8000/docs), and health is at [http://localhost:8000/health](http://localhost:8000/health). Migrations and user seeding run automatically before the API starts.

Seed credentials:

| Role | Email | Password |
|---|---|---|
| Admin | `admin@example.com` | `admin123` |
| Operator | `ops1@example.com` | `ops123` |
| Operator | `ops2@example.com` | `ops123` |
| Client | `client-a@example.com` | `client123` |
| Client | `client-b@example.com` | `client123` |

To import the supplied episodes, sign in as an operator in the API docs, authorize with the token from `POST /auth/login`, and call `POST /episodes/import` with `seed/episodes.csv`. The endpoint returns totals and a line-specific reason for every skipped row.

To reset local data:

```bash
docker compose down -v
```

## Tests

With Python 3.11+:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend && pytest
```

Tests use an isolated in-memory SQLite database and focus on authorization, ownership, transitions, assignment constraints, and import idempotency. CI also verifies that the frontend builds.

## API outline

- `POST /auth/login`, `GET /me`
- `GET/POST /requests`, `GET /requests/{id}`
- `POST /requests/{id}/status`, `GET /requests/{id}/history`
- `GET /episodes`, `POST /episodes/import`
- `POST /requests/{id}/assignments`
- `GET /analytics?start=YYYY-MM-DD&end=YYYY-MM-DD`
- `GET/POST/PATCH /users` (admin)
- `GET /health`

All routes other than login and health require a bearer token. Authorization and client ownership are checked by the API, independently of the UI.

## Production configuration

Set a strong random `SECRET_KEY`, restrict `CORS_ORIGINS`, terminate TLS at the ingress, and inject database credentials from a secret store. SQLite is used only by tests; Compose uses PostgreSQL. PostgreSQL is important in production for concurrent writes, robust constraints/locking, query planning, operational backups, and native analytics functions.

The CSV importer preloads existing external IDs in one query and inserts rows in one transaction. For five million episodes I would stream/chunk the file into a staging table, validate with SQL, and use PostgreSQL `COPY` plus `INSERT ... ON CONFLICT`; this avoids both the current request-size memory cost and per-row ORM overhead. Analytics are grouped in SQL and supported by date/robot/quality indexes. At sustained scale I would inspect `EXPLAIN ANALYZE`, add targeted composite/partial indexes, and pre-aggregate daily metrics if latency required it.

