from uuid import uuid4

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import event, null, select, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from mini_jira.api import create_app
from mini_jira.models import Base, Issue, Project
from mini_jira.seed import seed
from mini_jira.testing import validate_test_url


@pytest.mark.parametrize(
    "values",
    [
        {"key": "invalid", "name": "Name"},
        {"key": "OK", "name": " "},
        {"key": "OK", "name": None},
        {"key": "OK", "name": "Name", "description": None},
        {"key": "OK", "name": "Name", "description": "x" * 5001},
    ],
)
def test_project_constraints(engine, values):
    with Session(engine) as session:
        # Force SQL NULL; ORM None on a server-default column means use the default.
        values = {key: null() if value is None else value for key, value in values.items()}
        session.add(Project(**values))
        with pytest.raises(IntegrityError):
            session.commit()


@pytest.mark.parametrize(
    "values",
    [
        {"title": " "},
        {"title": "Valid", "status": "invalid"},
        {"title": "Valid", "description": "x" * 10001},
        {"title": "Valid", "project_id": uuid4()},
    ],
)
def test_issue_constraints(engine, values):
    with Session(engine) as session:
        p = Project(key="OK", name="Name")
        session.add(p)
        session.commit()
        session.add(Issue(**{"project_id": p.id, **values}))
        with pytest.raises(IntegrityError):
            session.commit()


def test_required_issue_fields_and_duplicate_key(engine):
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO projects (id, key, name) VALUES (:id, 'OK', 'Name')"), {"id": uuid4()}
        )
    for sql in [
        "INSERT INTO projects (id, key, name) VALUES (:id, 'OK', 'Other')",
        "INSERT INTO issues (id, project_id, title) VALUES (:id, NULL, 'Title')",
        "INSERT INTO issues (id, project_id, title) SELECT :id, id, NULL FROM projects LIMIT 1",
        "INSERT INTO issues (id, project_id, title, status) "
        "SELECT :id, id, 'Title', NULL FROM projects LIMIT 1",
    ]:
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(text(sql), {"id": uuid4()})


def test_seed_preserves_edits_and_is_idempotent(engine):
    seed(engine)
    with Session(engine) as session:
        issues = session.scalars(select(Issue)).all()
        assert {i.status for i in issues} == {"todo", "in_progress", "done"}
        edited_id = issues[0].id
        issues[0].title = "Keep my edit"
        issues[0].status = "done"
        session.commit()
    seed(engine)
    with Session(engine) as session:
        assert len(session.scalars(select(Project)).all()) == 1
        assert len(session.scalars(select(Issue)).all()) == 3
        assert session.get(Issue, edited_id).title == "Keep my edit"
        assert session.get(Issue, edited_id).status == "done"


def test_seed_with_existing_demo_project(engine):
    with Session(engine) as session:
        session.add(Project(key="DEMO", name="My project"))
        session.commit()
    seed(engine)
    seed(engine)
    with Session(engine) as session:
        assert session.scalar(select(Project)).name == "My project"
        assert len(session.scalars(select(Issue)).all()) == 3


def test_migration_round_trip_and_metadata(engine, migration_config):
    try:
        with engine.begin() as connection:
            migration_config.attributes["connection"] = connection
            command.downgrade(migration_config, "base")
            command.upgrade(migration_config, "head")
            command.upgrade(migration_config, "head")
            context = MigrationContext.configure(connection)
            assert compare_metadata(context, Base.metadata) == []
    finally:
        migration_config.attributes.pop("connection", None)


@pytest.mark.parametrize(
    "url, development",
    [
        ("sqlite:///test.db", "postgresql://localhost/dev"),
        ("postgresql://localhost/dev", "postgresql://localhost/dev"),
        ("postgresql://localhost/app_test", "postgresql://other-host/app_test"),
        ("postgresql://localhost/app_test?dbname=dev", "postgresql://localhost/dev"),
    ],
)
def test_unsafe_test_database_configuration_is_rejected(url, development):
    with pytest.raises(ValueError):
        validate_test_url(url, development)


def test_database_unavailable_responses(engine):
    # Exercise the HTTP behavior without stopping the shared PostgreSQL service.
    def fail(*args):
        raise OperationalError("SELECT", {}, Exception("private database details"))

    event.listen(engine, "before_cursor_execute", fail)
    try:
        with TestClient(create_app(engine)) as client:
            response = client.get("/health")
            assert response.status_code == 503
            assert response.json() == {"status": "unavailable"}
            response = client.get("/api/v1/projects")
            assert response.status_code == 503
            assert response.json() == {"detail": "Database unavailable"}
    finally:
        event.remove(engine, "before_cursor_execute", fail)
