"""Safety checks used before integration tests modify a database."""

from sqlalchemy.engine import URL, make_url


def validate_test_url(test_url: str, development_url: str) -> URL:
    test = make_url(test_url)
    development = make_url(development_url)
    if test.get_backend_name() != "postgresql":
        raise ValueError("Integration tests require PostgreSQL")
    if not test.database or not test.database.endswith("_test"):
        raise ValueError("Test database name must end with _test")
    # Deliberately conservative: reject matching database names even through host aliases.
    if test.database == development.database:
        raise ValueError("Test and development database names must differ")
    if test.query:
        raise ValueError("Test database URL query overrides are not permitted")
    return test
