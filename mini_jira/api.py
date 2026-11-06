from collections.abc import Generator
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from mini_jira.config import Settings
from mini_jira.database import make_engine
from mini_jira.models import Issue, Project
from mini_jira.schemas import (
    IssueCreate,
    IssueResponse,
    IssueUpdate,
    ProjectCreate,
    ProjectResponse,
    Status,
)


def create_app(engine: Engine | None = None) -> FastAPI:
    owns_engine = engine is None
    engine = (
        engine if engine is not None else make_engine(Settings().database_url.get_secret_value())
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        if owns_engine:
            engine.dispose()

    app = FastAPI(title="Mini Jira", version="0.1.0", lifespan=lifespan)

    def get_session() -> Generator[Session]:
        with Session(engine, expire_on_commit=False) as session:
            yield session

    Database = Annotated[Session, Depends(get_session)]

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, exc):
        return JSONResponse(status_code=503, content={"detail": "Database unavailable"})

    def require_project(session: Session, project_id: UUID) -> Project:
        project = session.get(Project, project_id)
        if project is None:
            raise HTTPException(404, "Project not found")
        return project

    def require_issue(session: Session, issue_id: UUID) -> Issue:
        issue = session.get(Issue, issue_id)
        if issue is None:
            raise HTTPException(404, "Issue not found")
        return issue

    @app.get("/health")
    def health():
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return JSONResponse(status_code=503, content={"status": "unavailable"})
        return {"status": "ok"}

    @app.post("/api/v1/projects", response_model=ProjectResponse, status_code=201)
    def create_project(body: ProjectCreate, session: Database):
        project = Project(**body.model_dump())
        session.add(project)
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            if getattr(exc.orig, "sqlstate", None) == "23505":
                raise HTTPException(409, "Project key already exists") from None
            raise
        return project

    @app.get("/api/v1/projects", response_model=list[ProjectResponse])
    def list_projects(session: Database):
        return session.scalars(select(Project).order_by(Project.created_at, Project.id)).all()

    @app.get("/api/v1/projects/{project_id}", response_model=ProjectResponse)
    def get_project(project_id: UUID, session: Database):
        return require_project(session, project_id)

    @app.post("/api/v1/projects/{project_id}/issues", response_model=IssueResponse, status_code=201)
    def create_issue(project_id: UUID, body: IssueCreate, session: Database):
        require_project(session, project_id)
        issue = Issue(project_id=project_id, **body.model_dump())
        session.add(issue)
        session.commit()
        return issue

    @app.get("/api/v1/projects/{project_id}/issues", response_model=list[IssueResponse])
    def list_issues(
        project_id: UUID, session: Database, status: Annotated[Status | None, Query()] = None
    ):
        require_project(session, project_id)
        statement = select(Issue).where(Issue.project_id == project_id)
        if status is not None:
            statement = statement.where(Issue.status == status)
        return session.scalars(statement.order_by(Issue.created_at, Issue.id)).all()

    @app.get("/api/v1/issues/{issue_id}", response_model=IssueResponse)
    def get_issue(issue_id: UUID, session: Database):
        return require_issue(session, issue_id)

    @app.patch("/api/v1/issues/{issue_id}", response_model=IssueResponse)
    def update_issue(issue_id: UUID, body: IssueUpdate, session: Database):
        issue = require_issue(session, issue_id)
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(issue, field, value)
        session.commit()
        session.refresh(issue)
        return issue

    return app
