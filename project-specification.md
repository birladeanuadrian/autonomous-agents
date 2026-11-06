# Mini Jira — project specification

## Purpose

Mini Jira is a small issue tracker API backed by PostgreSQL. It is the starting project for testing autonomous coding agents: each agent should be able to understand the application, make a bounded change, and demonstrate that the change works.

This document specifies a project to be implemented. It does not indicate that the application or the agent orchestration already exists. The sandbox setup notebook prepares environments; worktree transfer, task orchestration, and Git bundle retrieval remain separate implementation work.

## Initial scope

The first version supports:

- Creating, listing, and retrieving projects.
- Creating, listing, retrieving, and updating issues within a project.
- Moving issues between `todo`, `in_progress`, and `done`.
- Filtering a project's issues by status.
- Running the API directly with Python and PostgreSQL with Docker Compose.
- Applying database migrations, loading sample data, and running integration tests.

The first version has no frontend, authentication, users, assignees, permissions, comments, priorities, attachments, sprints, notifications, or external integrations. FastAPI's interactive documentation is the initial interface. These features can become later agent tasks.

## Technology

- Python and FastAPI for the HTTP API.
- SQLAlchemy for persistence, using synchronous database sessions.
- Psycopg for the PostgreSQL driver.
- Alembic for schema migrations.
- PostgreSQL as the application and integration-test database.
- pytest for tests.
- Docker Compose for development and test PostgreSQL services.

Choose supported versions during implementation, declare the Python version, pin container image versions, and commit a dependency lock file. Keep the application as a single service with a small, conventional package structure.

## Data model

### Project

| Field | Type | Rules |
| --- | --- | --- |
| `id` | UUID | Server-generated primary key; immutable. |
| `key` | String | Required, unique, immutable; 2–10 uppercase ASCII letters. Example: `DEMO`. |
| `name` | String | Required; 1–100 characters after trimming. |
| `description` | Text | Required in responses; defaults to an empty string; maximum 5,000 characters. |
| `created_at` | Timestamp with time zone | Set by the server; immutable. |

Project names do not have to be unique. Project keys do, with uniqueness enforced by PostgreSQL.

### Issue

| Field | Type | Rules |
| --- | --- | --- |
| `id` | UUID | Server-generated primary key; immutable. |
| `project_id` | UUID | Required foreign key to a project; immutable. |
| `title` | String | Required; 1–200 characters after trimming. |
| `description` | Text | Required in responses; defaults to an empty string; maximum 10,000 characters. |
| `status` | String | One of `todo`, `in_progress`, `done`; defaults to `todo`. |
| `created_at` | Timestamp with time zone | Set by the server; immutable. |
| `updated_at` | Timestamp with time zone | Initially equals `created_at`; changes when persisted issue values change. |

Use UUIDs as issue identifiers in the initial version. Human-readable identifiers such as `DEMO-123` are a possible extension.

Enforce required values, project-key uniqueness, foreign keys, and valid issue statuses in the database as well as in API validation. Index issues by project and creation time. Return timestamps as ISO 8601 UTC strings.

## API contract

All application routes use the `/api/v1` prefix. Requests and responses use JSON. Resource responses expose exactly the fields listed in the data model.

| Method | Route | Behavior | Success |
| --- | --- | --- | --- |
| `POST` | `/api/v1/projects` | Create a project. | `201`, project object |
| `GET` | `/api/v1/projects` | List projects. | `200`, project array |
| `GET` | `/api/v1/projects/{project_id}` | Retrieve a project. | `200`, project object |
| `POST` | `/api/v1/projects/{project_id}/issues` | Create an issue in a project. | `201`, issue object |
| `GET` | `/api/v1/projects/{project_id}/issues` | List issues; optional `status` query parameter. | `200`, issue array |
| `GET` | `/api/v1/issues/{issue_id}` | Retrieve an issue. | `200`, issue object |
| `PATCH` | `/api/v1/issues/{issue_id}` | Update an issue's title, description, or status. | `200`, issue object |
| `GET` | `/health` | Verify API readiness and database connectivity. | `200`, `{"status":"ok"}` |

Creation payloads accept only the writable fields: `key`, `name`, and optional `description` for projects; `title`, optional `description`, and optional `status` for issues. Generate IDs and timestamps on the server.

Additional behavior:

- Trim project names and issue titles before validating and storing them. Preserve description whitespace. Reject lowercase project keys rather than silently converting them.
- Reject unknown request fields, explicit `null` values, and an empty PATCH payload with `422`. Omitted PATCH fields retain their existing values.
- Permit any transition between valid statuses, including reopening completed issues.
- Return lists in ascending `created_at` order, with `id` as a stable tie-breaker. An empty list is `[]`.
- Return `404` for missing projects or issues. Listing issues for a missing project also returns `404`.
- Return `409` for a duplicate project key, including concurrent attempts to create the same key.
- Return `422` for invalid field values, malformed UUIDs, or invalid status filters.
- Use FastAPI's `detail` error format: a message for resource/conflict errors and the standard validation error list for validation failures. Do not expose database errors or stack traces.
- Return `503` from `/health` with `{"status":"unavailable"}` when the database cannot be reached.

Project updates, deletion, cross-project issue searches, and pagination are outside the initial scope. Unbounded lists are acceptable for this small test fixture; pagination is a later task.

## Python runtime, Docker Compose, and configuration

Run the API directly in a local Python virtual environment. Provide a module entry point so `python -m mini_jira` starts the FastAPI application through Uvicorn on `127.0.0.1:8000`. Run migrations, sample-data loading, and tests in the same Python environment. The API does not require a Dockerfile or a Compose service.

Provide a `compose.yaml` with:

- A `db` service running PostgreSQL, with a health check and a named volume for persistent data. Publish its port on `127.0.0.1:5432` so the local Python process can connect.
- A `test` profile containing a separate PostgreSQL service named `test-db`, published on `127.0.0.1:5433`. Test data must never share the development database or its volume.
- Configurable host ports to accommodate existing local PostgreSQL instances.

`docker compose up -d --wait db` must start a healthy development database. Apply migrations explicitly with `python -m alembic upgrade head` before starting the API. Repeated database startup must preserve data, and repeated migration runs must safely apply only outstanding migrations. Keep schema changes in Alembic migrations; do not use ORM table creation as the startup migration mechanism.

Read configuration from environment variables, with local `.env` loading for Python commands. Commit `.env.example` with disposable local database credentials, separate `DATABASE_URL` and `TEST_DATABASE_URL` values, and documented defaults. Use loopback database addresses for local execution and document an explicit connection override for sandbox workers. Ignore `.env` and keep real credentials out of source control, images, templates, and Git bundles. The application does not need third-party credentials or runtime internet access.

## Sample data and developer commands

Provide an explicit, repeatable seed command that creates a `DEMO` project and at least three issues covering all statuses. Running it twice must not duplicate records or overwrite changes to existing sample issues. Do not seed automatically during startup.

Document these workflows in the application's README:

1. Create and activate a Python virtual environment, install locked dependencies, and copy `.env.example` to `.env`. Include the exact commands for the chosen dependency manager.
2. Start PostgreSQL with `docker compose up -d --wait db`.
3. Apply migrations with `python -m alembic upgrade head`.
4. Start the API with `python -m mini_jira`, open `http://localhost:8000/docs`, and check `/health`.
5. Run the seed command with `python -m mini_jira.seed` and try creating and updating an issue.
6. Start the test database with `docker compose --profile test up -d --wait test-db`, then run integration tests locally with `python -m pytest`.
7. Create and apply an Alembic migration from the local Python environment.
8. Stop the API with Ctrl+C and stop database services while retaining data with `docker compose --profile test down`.
9. Explicitly reset development data with `docker compose --profile test down --volumes`, explaining that it deletes local database data, including any test volumes.

The test setup must use `TEST_DATABASE_URL`, reject configuration targeting the development database, and apply migrations to the test database before tests run. The test command must return a nonzero exit code on failure and work on repeated runs. Tests must not require a separately running API process.

## Verification and acceptance criteria

The initial implementation is complete when:

- A fresh checkout runs through the documented virtual-environment setup, database startup, migration, and Python API commands without manual SQL.
- Compose runs only PostgreSQL services; the API, migrations, seed command, and tests run directly with Python.
- Interactive API documentation and readiness checks work.
- Projects and issues can be created and retrieved, and data survives a service restart.
- Issue edits preserve omitted fields, status filtering returns the expected records, and issues remain isolated by project.
- Integration tests use real PostgreSQL and cover the core workflow, validation, missing resources, duplicate keys, stable ordering, and PATCH behavior.
- Tests verify database constraints and demonstrate that the test environment does not use development data.
- Migrations build the schema from an empty database, and the seed command is repeatable.
- The README contains the commands and expected outcomes needed to reproduce these checks.

Keep testing focused on observable behavior and database guarantees. A separate frontend, deployment pipeline, and performance benchmark suite are unnecessary for this version.

## Follow-up tasks for autonomous agents

Use the completed initial implementation as the baseline. Each follow-up task should define its behavior, migration requirements, and acceptance criteria before being assigned.

| Task | Example acceptance criteria |
| --- | --- |
| Add issue priorities | Existing issues receive a default priority; clients can set and filter valid priorities. |
| Add comments | Comments belong to an existing issue, have timestamps, and can be listed in a defined order. |
| Add pagination | List endpoints have documented defaults, bounds, ordering, and response metadata. |
| Add an activity log | Each actual status change records the old and new values atomically with the issue update. |
| Add human-readable issue keys | Concurrent issue creation produces unique project-local numbers. |
| Add project deletion | Explicitly specified deletion rules preserve referential integrity and have integration coverage. |

The intended agent workflow uses a dedicated Git worktree in an isolated Docker sandbox for each assignment. Agents deliver changes as Git bundles for host-side review and integration; they do not clone, pull, or push through GitHub. Apply and verify the sandbox's network policy separately for each worker, following `sandbox-setup.ipynb` and `WHITELISTED_DOMAINS.md`.

Keep Mini Jira's application Compose services separate from Docker Sandboxes infrastructure. The implementation must document how the chosen worker environment runs or reaches its test services; do not assume nested Docker or access to the host Docker socket is available.
