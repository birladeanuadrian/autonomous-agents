"""Create deterministic sample records without overwriting existing records."""

from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from mini_jira.config import Settings
from mini_jira.database import make_engine
from mini_jira.models import Issue, Project

NAMESPACE = UUID("522bec37-3496-43cb-b564-e73a4d905e63")


def seed(engine: Engine) -> None:
    with Session(engine) as session, session.begin():
        session.execute(
            insert(Project)
            .values(id=uuid5(NAMESPACE, "DEMO"), key="DEMO", name="Demo project")
            .on_conflict_do_nothing(index_elements=[Project.key])
        )
        project = session.scalar(select(Project).where(Project.key == "DEMO"))
        for status, title in [
            ("todo", "Write the first issue"),
            ("in_progress", "Try updating an issue"),
            ("done", "Start Mini Jira"),
        ]:
            session.execute(
                insert(Issue)
                .values(
                    id=uuid5(NAMESPACE, f"{project.id}/{status}"),
                    project_id=project.id,
                    title=title,
                    status=status,
                )
                .on_conflict_do_nothing(index_elements=[Issue.id])
            )


def main() -> None:
    engine = make_engine(Settings().database_url.get_secret_value())
    try:
        seed(engine)
        print("DEMO project and sample issues are ready.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
