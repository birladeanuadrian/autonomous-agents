from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("key ~ '^[A-Z]{2,10}$'", name="ck_projects_key"),
        CheckConstraint("length(btrim(name)) BETWEEN 1 AND 100", name="ck_projects_name"),
        CheckConstraint("length(description) <= 5000", name="ck_projects_description"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    key: Mapped[str] = mapped_column(String(10), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Issue(Base):
    __tablename__ = "issues"
    __table_args__ = (
        CheckConstraint("length(btrim(title)) BETWEEN 1 AND 200", name="ck_issues_title"),
        CheckConstraint("length(description) <= 10000", name="ck_issues_description"),
        CheckConstraint("status IN ('todo', 'in_progress', 'done')", name="ck_issues_status"),
        Index("ix_issues_project_created", "project_id", "created_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, server_default="")
    status: Mapped[str] = mapped_column(String(20), server_default="todo")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
