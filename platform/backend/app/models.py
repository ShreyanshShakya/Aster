import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class JobStatus(str, enum.Enum):
    DRAFT = "draft"
    QUEUED = "queued"
    ASSIGNED = "assigned"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class IdMixin:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(IdMixin, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    display_name: Mapped[str] = mapped_column(String(120))


class Project(IdMixin, Base):
    __tablename__ = "projects"
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class ResearchRun(IdMixin, Base):
    __tablename__ = "research_runs"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    question: Mapped[str] = mapped_column(Text)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.QUEUED)
    plan: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Job(IdMixin, Base):
    __tablename__ = "jobs"
    research_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("research_runs.id"), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(80), default="dummy-research")
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.QUEUED, index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    worker_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workers.id"), nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class Worker(IdMixin, Base):
    __tablename__ = "workers"
    name: Mapped[str] = mapped_column(String(160), unique=True)
    capabilities: Mapped[dict] = mapped_column(JSON, default=dict)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Artifact(IdMixin, Base):
    __tablename__ = "artifacts"
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    storage_key: Mapped[str] = mapped_column(String(512), unique=True)
    media_type: Mapped[str] = mapped_column(String(160))


class Report(IdMixin, Base):
    __tablename__ = "reports"
    research_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_runs.id"), index=True)
    markdown_artifact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("artifacts.id"), nullable=True)
    json_artifact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("artifacts.id"), nullable=True)


class JobEvent(IdMixin, Base):
    __tablename__ = "job_events"
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id"), index=True)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus))
    message: Mapped[str] = mapped_column(Text)


class Paper(IdMixin, Base):
    __tablename__ = "papers"
    source: Mapped[str] = mapped_column(String(64), index=True)
    external_id: Mapped[str] = mapped_column(String(256))
    doi: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)
    title: Mapped[str] = mapped_column(Text)
    authors: Mapped[list] = mapped_column(JSON, default=list)
    publication_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    cited_by_count: Mapped[int] = mapped_column(Integer, default=0)
    raw_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_papers_source_external_id"),)


class ResearchPaper(IdMixin, Base):
    __tablename__ = "research_papers"
    research_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_runs.id"), index=True)
    paper_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("papers.id"), index=True)
    rank: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float)
    relevance: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__ = (UniqueConstraint("research_run_id", "paper_id", name="uq_research_papers_run_paper"),)


class Knowledge(IdMixin, Base):
    __tablename__ = "knowledge"
    research_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_runs.id"), index=True)
    paper_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("papers.id"), nullable=True, index=True)
    extracted: Mapped[dict] = mapped_column(JSON, default=dict)


class Hypothesis(IdMixin, Base):
    __tablename__ = "hypotheses"
    research_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_runs.id"), index=True)
    statement: Mapped[str] = mapped_column(Text)
    rationale: Mapped[str] = mapped_column(Text)
    expected_improvement: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk: Mapped[str | None] = mapped_column(Text, nullable=True)
    novelty: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)


class ExperimentPlan(IdMixin, Base):
    __tablename__ = "experiment_plans"
    research_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_runs.id"), index=True)
    configuration: Mapped[dict] = mapped_column(JSON, default=dict)
    datasets: Mapped[list] = mapped_column(JSON, default=list)
    metrics: Mapped[list] = mapped_column(JSON, default=list)
    resource_estimate: Mapped[dict] = mapped_column(JSON, default=dict)


class ResearchEvent(IdMixin, Base):
    __tablename__ = "research_events"
    research_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_runs.id"), index=True)
    stage: Mapped[str] = mapped_column(String(80))
    message: Mapped[str] = mapped_column(Text)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
