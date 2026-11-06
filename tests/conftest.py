from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

from mini_jira.api import create_app
from mini_jira.config import Settings
from mini_jira.database import make_engine
from mini_jira.testing import validate_test_url


@pytest.fixture(scope="session")
def migration_config():
    return Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))


@pytest.fixture(scope="session")
def engine(migration_config):
    settings = Settings()
    url = validate_test_url(
        settings.test_database_url.get_secret_value(), settings.database_url.get_secret_value()
    )
    engine = make_engine(url.render_as_string(hide_password=False))
    try:
        with engine.begin() as connection:
            actual = connection.scalar(text("SELECT current_database()"))
            if actual != url.database:
                raise ValueError("Connected database does not match the validated test database")
            migration_config.attributes["connection"] = connection
            command.upgrade(migration_config, "head")
        migration_config.attributes.pop("connection", None)
        yield engine
    finally:
        migration_config.attributes.pop("connection", None)
        engine.dispose()


@pytest.fixture(autouse=True)
def clean_database(engine):
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE issues, projects"))
    yield


@pytest.fixture
def client(engine):
    with TestClient(create_app(engine)) as client:
        yield client
