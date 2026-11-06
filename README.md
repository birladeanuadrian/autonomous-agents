# Autonomous coding agents

This repository demonstrates autonomous coding agents running in isolated Docker sandboxes, with limited network access and Git bundles for delivering their work.

Start with [sandbox-setup.ipynb](sandbox-setup.ipynb). The notebook introduces Docker Sandboxes from scratch and walks through installation, locked-down networking, the domain allowlist, policy checks, saving a template, reuse, and cleanup. Open it in PyCharm, Jupyter, or a notebook viewer and copy the command blocks into a host Bash terminal as you read. No Python kernel is required.

The setup walkthrough prepares the environment. Git worktree transfer, task execution, and bundle retrieval will be covered separately.

See [WHITELISTED_DOMAINS.md](WHITELISTED_DOMAINS.md) for approved domains and proposed additions.

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

Creation returns HTTP 201. Status changes return HTTP 200 and update `updated_at`; omitted fields remain unchanged. Duplicate project keys return 409, missing resources return 404, and invalid requests return 422. The initial version has no authentication or frontend; use it as a local exercise.

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

The commands above describe local development. A Docker Sandbox worker runs Python in its own environment and cannot reach the host database through `127.0.0.1`. Do not assume the worker has Docker, nested Docker support, or access to the host Docker socket.

The host orchestration must provision a disposable PostgreSQL instance per worker, provide a database address reachable from that worker, and explicitly permit that connection in the worker's network policy. Set `DATABASE_URL` and `TEST_DATABASE_URL` to the provisioned endpoints, using separate development and test databases and a test name ending in `_test`. Loopback-only Compose ports deliberately do not provide remote worker access. The implementation of this provisioning and sandbox networking remains part of the future orchestration work; the existing setup notebook does not implement it.
