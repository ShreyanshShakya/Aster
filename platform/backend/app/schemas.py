from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import JobStatus


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: EmailStr
    display_name: str


class ProfileUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = None


class ProjectResponse(ProjectCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: datetime


class ResearchCreate(BaseModel):
    project_id: UUID
    question: str = Field(min_length=10, max_length=10_000)


class PlanValidationCreate(BaseModel):
    executor: str = Field(default="local-plan-validation", max_length=80)


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    research_run_id: UUID | None
    kind: str
    status: JobStatus
    payload: dict
    result: dict | None
    error: str | None
    created_at: datetime


class JobEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    job_id: UUID
    status: JobStatus
    message: str
    created_at: datetime


class WorkerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    capabilities: dict
    last_heartbeat_at: datetime | None
    created_at: datetime


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    research_run_id: UUID
    markdown_artifact_id: UUID | None
    json_artifact_id: UUID | None
    created_at: datetime


class ResearchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    question: str
    status: JobStatus
    plan: dict | None
    created_at: datetime


class PaperResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    source: str
    title: str
    authors: list
    publication_year: int | None
    abstract: str | None
    url: str | None
    cited_by_count: int


class ResearchEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    stage: str
    message: str
    data: dict
    created_at: datetime
