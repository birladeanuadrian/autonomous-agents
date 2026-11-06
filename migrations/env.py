from alembic import context

from mini_jira.config import Settings
from mini_jira.database import make_engine
from mini_jira.models import Base

config = context.config
target_metadata = Base.metadata


def run_migrations() -> None:
    # Tests supply their already-validated connection; CLI uses development configuration.
    connection = config.attributes.get("connection")
    if connection is not None:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    elif context.is_offline_mode():
        context.configure(
            url=Settings().database_url.get_secret_value(),
            target_metadata=target_metadata,
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
        )
        with context.begin_transaction():
            context.run_migrations()
    else:
        engine = make_engine(Settings().database_url.get_secret_value())
        try:
            with engine.connect() as connection:
                context.configure(connection=connection, target_metadata=target_metadata)
                with context.begin_transaction():
                    context.run_migrations()
        finally:
            engine.dispose()


run_migrations()
