"""Create projects, issues, and issue timestamp maintenance."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("key", sa.String(10), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("key ~ '^[A-Z]{2,10}$'", name="ck_projects_key"),
        sa.CheckConstraint("length(btrim(name)) BETWEEN 1 AND 100", name="ck_projects_name"),
        sa.CheckConstraint("length(description) <= 5000", name="ck_projects_description"),
    )
    op.create_table(
        "issues",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="todo"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("length(btrim(title)) BETWEEN 1 AND 200", name="ck_issues_title"),
        sa.CheckConstraint("length(description) <= 10000", name="ck_issues_description"),
        sa.CheckConstraint("status IN ('todo', 'in_progress', 'done')", name="ck_issues_status"),
    )
    op.create_index("ix_issues_project_created", "issues", ["project_id", "created_at", "id"])
    op.execute("""
        CREATE FUNCTION maintain_issue_timestamps() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF ROW(NEW.title, NEW.description, NEW.status)
               IS DISTINCT FROM ROW(OLD.title, OLD.description, OLD.status) THEN
                NEW.updated_at := clock_timestamp();
            ELSE
                NEW.updated_at := OLD.updated_at;
            END IF;
            RETURN NEW;
        END;
        $$;
        CREATE TRIGGER issue_timestamps BEFORE UPDATE ON issues
        FOR EACH ROW EXECUTE FUNCTION maintain_issue_timestamps();
    """)


def downgrade() -> None:
    op.drop_table("issues")
    op.execute("DROP FUNCTION maintain_issue_timestamps()")
    op.drop_table("projects")
