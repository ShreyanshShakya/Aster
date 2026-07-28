"""Initial Aster Platform schema.

Revision ID: 20260723_0001
Revises:
Create Date: 2026-07-23
"""
from alembic import op

from app.database import Base
import app.models  # noqa: F401 - register mapped tables


revision = "20260723_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create only the tables that existed in the initial platform release."""
    initial_table_names = (
        "users", "projects", "research_runs", "workers", "jobs", "artifacts", "reports", "job_events",
    )
    Base.metadata.create_all(bind=op.get_bind(), tables=[Base.metadata.tables[name] for name in initial_table_names])


def downgrade() -> None:
    initial_table_names = (
        "job_events", "reports", "artifacts", "jobs", "workers", "research_runs", "projects", "users",
    )
    Base.metadata.drop_all(bind=op.get_bind(), tables=[Base.metadata.tables[name] for name in initial_table_names])
