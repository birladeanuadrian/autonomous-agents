# Autonomous coding agents

This repository demonstrates autonomous coding agents running in isolated Docker sandboxes, with limited network access and readable Git patches for delivering their work.

Start with [sandbox-setup.ipynb](sandbox-setup.ipynb). The notebook introduces Docker Sandboxes from scratch and walks through installation, locked-down networking, the domain allowlist, policy checks, saving a template, reuse, and cleanup. Open it in PyCharm, Jupyter, or a notebook viewer and copy the command blocks into a host Bash terminal as you read. No Python kernel is required.

The setup walkthrough prepares the environment. The MCP server implements worker
preparation, task launch, and delivery retrieval; integration remains manual.

See [WHITELISTED_DOMAINS.md](WHITELISTED_DOMAINS.md) for approved domains and proposed additions.

The [agent communication MCP server](agent_mcp/README.md) is a separate Python
stdio server that starts tasks in isolated workers using the saved template.
Status and result tools report progress and retrieve delivery files to the host.

## Mini Jira

Mini Jira is the starting application for agent exercises: a FastAPI issue tracker with projects, issues, and status updates. The API, migrations, seed command, and tests run directly with Python. Docker Compose runs only PostgreSQL. See [project-specification.md](project-specification.md) for the full contract.

### Prerequisites

Install Python 3.14, [uv](https://docs.astral.sh/uv/getting-started/installation/), and Docker Desktop with Docker Compose supporting `--wait`. Run all commands below from this repository's root. These instructions use a Bash or Zsh terminal on macOS/Linux.

### Start from a fresh checkout

```bash
uv sync --locked
source .venv/bin/activate
cp .env.example .env
docker compose up -d --wait db
python -m alembic upgrade head
python -m mini_jira
```

`uv sync --locked` creates `.venv` and installs the exact application and development dependencies from `uv.lock`. Copy `.env.example` only on the first setup; keep your existing `.env` on later runs. The database command waits until PostgreSQL is healthy. Alembic creates the schema on the first run and applies only outstanding migrations on subsequent runs. The final command starts the API on `127.0.0.1:8000` and keeps the terminal occupied. Press Ctrl+C to stop it.

Open [the interactive API docs](http://localhost:8000/docs). `GET /health` returns `{"status":"ok"}` when PostgreSQL is reachable and HTTP 503 otherwise.

In a second terminal, activate the environment and load sample data:

```bash
source .venv/bin/activate
python -m mini_jira.seed
```

This creates a `DEMO` project and three issues, one per status. Repeating the command preserves existing sample records and edits.

### Try the API

Create a project:

```bash
curl -sS http://localhost:8000/api/v1/projects \
  -H 'Content-Type: application/json' \
  -d '{"key":"WORK","name":"My project"}'
```

Copy the returned UUID into `PROJECT_ID`, then create an issue:

```bash
PROJECT_ID=replace-with-project-uuid
curl -sS "http://localhost:8000/api/v1/projects/$PROJECT_ID/issues" \
  -H 'Content-Type: application/json' \
  -d '{"title":"Try Mini Jira"}'
```

Copy the issue UUID into `ISSUE_ID`, then update its status and list completed issues:

```bash
ISSUE_ID=replace-with-issue-uuid
curl -sS -X PATCH "http://localhost:8000/api/v1/issues/$ISSUE_ID" \
  -H 'Content-Type: application/json' \
  -d '{"status":"done"}'
curl -sS "http://localhost:8000/api/v1/projects/$PROJECT_ID/issues?status=done"
```

Creation returns HTTP 201. Status changes return HTTP 200 and update `updated_at`; omitted fields remain unchanged. Duplicate project keys return 409, missing resources return 404, and invalid requests return 422. The application has no authentication; use it as a local exercise.

### Frontend

With the API and database running as described above, install Node.js 20.19+ or 22.12+ and start the frontend in a second terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open the local URL printed by Vite (normally http://localhost:5173). Vite proxies same-origin `/api` requests to `http://127.0.0.1:8000`; set `VITE_API_PROXY_TARGET` when starting Vite to use a different FastAPI address. The UI supports project creation and navigation, issue creation and editing, all status transitions, and status filtering. Names and titles are trimmed; descriptions retain whitespace. Project keys must be 2–10 uppercase letters. The interface displays API validation, conflict, and missing-resource errors.

Run `npm test` for mocked API interaction tests and `npm run build` for TypeScript checking and a production build. Serve `frontend/dist` with a web server and configure that same origin to reverse proxy `/api/` to FastAPI, preserving the path. Vite's development proxy does not apply to production hosting. The frontend never calls `/health`.

### Configuration

Both Compose and Python commands read `.env`. Python settings also accept environment-variable overrides. `.env.example` contains disposable local credentials and separate database URLs:

- `DATABASE_URL`: development database on `127.0.0.1:5432/mini_jira`.
- `TEST_DATABASE_URL`: test database on `127.0.0.1:5433/mini_jira_test`.
- `DB_PORT` and `TEST_DB_PORT`: published PostgreSQL host ports.
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB`: development container initialization settings. The test container uses the same local user/password and a fixed `mini_jira_test` database name.

If a port is occupied, change its port setting and the corresponding database URL together. Changing initialization credentials does not change an existing PostgreSQL volume; keep the existing credentials or explicitly reset disposable data. Never commit real credentials.

### Run tests and checks

```bash
source .venv/bin/activate
docker compose --profile test up -d --wait test-db
python -m pytest
python -m ruff check .
python -m ruff format --check .
```

Tests run locally against real PostgreSQL without a separate API process. They apply Alembic migrations, clear only the test tables between cases, and exercise API workflows, validation, project isolation, ordering, concurrent duplicate keys, constraints, seed behavior, database failure responses, and migration round trips. A failing test produces a nonzero exit code.

The test URL must use PostgreSQL, name a database ending in `_test`, have no query overrides, and differ from the development database name. Tests verify the connected database name before modifying it. Use a dedicated disposable database: tests truncate its project/issue tables and the migration test rebuilds its schema. Development services and data are separate. Test PostgreSQL uses temporary memory-backed storage, discarded when its container is stopped.

### Database migrations

After changing the SQLAlchemy models, create a migration against the running development database:

```bash
python -m alembic revision --autogenerate -m "Describe the schema change"
```

Review the generated file in `migrations/versions/`, including its downgrade. Alembic does not generate changes to PostgreSQL trigger functions automatically; maintain these explicitly. Apply the migration and verify that models and migrations agree:

```bash
python -m alembic upgrade head
python -m alembic check
```

Migrations own the schema. API startup never creates tables or applies migrations. The initial migration also installs a trigger that updates issue timestamps only when editable values actually change.

### Stop and reset

Stop the API with Ctrl+C. Stop all database services while keeping development data:

```bash
docker compose --profile test down
```

To delete all local development database data as well:

```bash
docker compose --profile test down --volumes
```

The second command is destructive. On the next startup, reapply migrations and optionally rerun the seed command. Ordinary database/container restarts retain development data in the named volume.

### Running inside an agent sandbox

Each worker owns its entire application stack inside its own sandbox and private Docker Engine. The MCP server creates the sandbox and checkout and retrieves delivery; it does not provision databases. There is no host, shared, or external PostgreSQL service. The loopback addresses, ports, and Compose volume names above are local to that worker's engine and sandbox; independent workers can use the same defaults without cross-worker network permissions.

When the assignment needs the stack, verify `docker version` and `docker compose version`, copy `.env.example` to a local ignored `.env`, and follow the setup above inside the worker. Start both `db` and `test-db` with Compose's `--wait`; apply migrations and run `python -m alembic check` against the development database. Seed only if useful. Start the API and frontend directly in the sandbox; check `/health`, the UI in a browser using the real API, and the backend and frontend tests/build as applicable. The host cannot open sandbox loopback directly. Report any blocked image download and its destination, method and path; do not change policy yourself. Never include `.env`, runtime database state, or credentials in a patch or template.

Stop only services and processes started by the worker. `docker compose --profile test down --volumes` removes its disposable development volume; test data is memory-backed. Report cleanup and any checks that could not run.
