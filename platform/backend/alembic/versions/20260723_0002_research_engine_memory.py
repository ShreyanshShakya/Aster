"""Add persistent research-engine memory.

Revision ID: 20260723_0002
Revises: 20260723_0001
Create Date: 2026-07-23
"""
import sqlalchemy as sa
from alembic import op


revision = "20260723_0002"
down_revision = "20260723_0001"
branch_labels = None
depends_on = None


def identity_columns():
    return [
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table("papers", *identity_columns(),
        sa.Column("source", sa.String(length=64), nullable=False), sa.Column("external_id", sa.String(length=256), nullable=False),
        sa.Column("doi", sa.String(length=512), nullable=True), sa.Column("title", sa.Text(), nullable=False), sa.Column("authors", sa.JSON(), nullable=False),
        sa.Column("publication_year", sa.Integer(), nullable=True), sa.Column("abstract", sa.Text(), nullable=True), sa.Column("url", sa.String(length=2048), nullable=True),
        sa.Column("cited_by_count", sa.Integer(), nullable=False), sa.Column("raw_metadata", sa.JSON(), nullable=False),
        sa.UniqueConstraint("source", "external_id", name="uq_papers_source_external_id"))
    op.create_index("ix_papers_source", "papers", ["source"])
    op.create_index("ix_papers_doi", "papers", ["doi"])
    op.create_table("research_papers", *identity_columns(),
        sa.Column("research_run_id", sa.Uuid(), nullable=False), sa.Column("paper_id", sa.Uuid(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False), sa.Column("score", sa.Float(), nullable=False), sa.Column("relevance", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["research_run_id"], ["research_runs.id"]), sa.ForeignKeyConstraint(["paper_id"], ["papers.id"]),
        sa.UniqueConstraint("research_run_id", "paper_id", name="uq_research_papers_run_paper"))
    op.create_index("ix_research_papers_research_run_id", "research_papers", ["research_run_id"])
    op.create_index("ix_research_papers_paper_id", "research_papers", ["paper_id"])
    for name, paper_nullable in (("knowledge", True), ("hypotheses", False), ("experiment_plans", False), ("research_events", False)):
        if name == "knowledge":
            op.create_table(name, *identity_columns(), sa.Column("research_run_id", sa.Uuid(), nullable=False), sa.Column("paper_id", sa.Uuid(), nullable=paper_nullable), sa.Column("extracted", sa.JSON(), nullable=False), sa.ForeignKeyConstraint(["research_run_id"], ["research_runs.id"]), sa.ForeignKeyConstraint(["paper_id"], ["papers.id"]))
        elif name == "hypotheses":
            op.create_table(name, *identity_columns(), sa.Column("research_run_id", sa.Uuid(), nullable=False), sa.Column("statement", sa.Text(), nullable=False), sa.Column("rationale", sa.Text(), nullable=False), sa.Column("expected_improvement", sa.Text(), nullable=True), sa.Column("risk", sa.Text(), nullable=True), sa.Column("novelty", sa.Text(), nullable=True), sa.Column("evidence", sa.JSON(), nullable=False), sa.ForeignKeyConstraint(["research_run_id"], ["research_runs.id"]))
        elif name == "experiment_plans":
            op.create_table(name, *identity_columns(), sa.Column("research_run_id", sa.Uuid(), nullable=False), sa.Column("configuration", sa.JSON(), nullable=False), sa.Column("datasets", sa.JSON(), nullable=False), sa.Column("metrics", sa.JSON(), nullable=False), sa.Column("resource_estimate", sa.JSON(), nullable=False), sa.ForeignKeyConstraint(["research_run_id"], ["research_runs.id"]))
        else:
            op.create_table(name, *identity_columns(), sa.Column("research_run_id", sa.Uuid(), nullable=False), sa.Column("stage", sa.String(length=80), nullable=False), sa.Column("message", sa.Text(), nullable=False), sa.Column("data", sa.JSON(), nullable=False), sa.ForeignKeyConstraint(["research_run_id"], ["research_runs.id"]))
        op.create_index(f"ix_{name}_research_run_id", name, ["research_run_id"])
    op.create_index("ix_knowledge_paper_id", "knowledge", ["paper_id"])


def downgrade() -> None:
    for name in ("research_events", "experiment_plans", "hypotheses", "knowledge", "research_papers"):
        op.drop_table(name)
    op.drop_table("papers")
