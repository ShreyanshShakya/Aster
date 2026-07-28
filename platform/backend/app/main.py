import asyncio
import json
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import create_access_token, decode_access_token, get_current_user, hash_password, verify_password
from app.database import get_db
from app.dmlf_client import cancel as cancel_dmlf
from app.executors import executor_by_id, serialized_executors
from app.models import Artifact, ExperimentPlan, Hypothesis, Job, JobEvent, JobStatus, Paper, Project, Report, ResearchEvent, ResearchPaper, ResearchRun, User, Worker
from app.queue import redis_client
from app.services import record_event
from app.schemas import (
    JobResponse,
    JobEventResponse,
    LoginRequest,
    ProjectCreate,
    ProjectResponse,
    ProfileUpdate,
    ResearchCreate,
    ResearchEventResponse,
    ResearchResponse,
    PaperResponse,
    PlanValidationCreate,
    ReportResponse,
    SignupRequest,
    TokenResponse,
    UserResponse,
    WorkerResponse,
)
from app.storage import get_artifact


app = FastAPI(title="Aster Platform API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "aster-platform-api"}


@app.get("/executors")
def list_executors(user: User = Depends(get_current_user)) -> list[dict]:
    return serialized_executors()


@app.websocket("/ws/jobs")
async def job_events(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return
    try:
        user_id = decode_access_token(token)
    except HTTPException:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    pubsub = redis_client().pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(f"aster:users:{user_id}")
    try:
        while True:
            message = await asyncio.to_thread(pubsub.get_message, timeout=1.0)
            if message and message.get("type") == "message":
                await websocket.send_text(message["data"])
            await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        pass
    finally:
        pubsub.close()


@app.post("/auth/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> TokenResponse:
    if db.scalar(select(User).where(User.email == payload.email)):
        raise HTTPException(status_code=409, detail="Email is already registered")
    user = User(email=str(payload.email), display_name=payload.display_name, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_access_token(user.id))


@app.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return TokenResponse(access_token=create_access_token(user.id))


@app.get("/profile", response_model=UserResponse)
def profile(user: User = Depends(get_current_user)) -> User:
    return user


@app.patch("/profile", response_model=UserResponse)
def update_profile(payload: ProfileUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    user.display_name = payload.display_name.strip()
    db.commit()
    db.refresh(user)
    return user


@app.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Project:
    project = Project(owner_id=user.id, **payload.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@app.get("/projects", response_model=list[ProjectResponse])
def list_projects(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Project]:
    return list(db.scalars(select(Project).where(Project.owner_id == user.id).order_by(Project.created_at.desc())))


@app.post("/research", response_model=ResearchResponse, status_code=status.HTTP_202_ACCEPTED)
def create_research(payload: ResearchCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ResearchRun:
    project = db.get(Project, payload.project_id)
    if project is None or project.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    run = ResearchRun(project_id=project.id, question=payload.question, status=JobStatus.QUEUED)
    db.add(run)
    db.flush()
    job = Job(research_run_id=run.id, kind="dummy-research", status=JobStatus.QUEUED, payload={"question": run.question})
    db.add(job)
    db.commit()
    db.refresh(run)
    return run


@app.post("/research/start", response_model=ResearchResponse, status_code=status.HTTP_202_ACCEPTED)
def start_research_engine(payload: ResearchCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ResearchRun:
    project = db.get(Project, payload.project_id)
    if project is None or project.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    run = ResearchRun(project_id=project.id, question=payload.question, status=JobStatus.QUEUED)
    db.add(run); db.flush()
    db.add(Job(research_run_id=run.id, kind="research-plan", status=JobStatus.QUEUED, payload={"question": run.question, "engine": "milestone-2"}))
    db.commit(); db.refresh(run)
    return run


@app.post("/research/{run_id}/validate", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
def validate_research_plan(run_id: UUID, payload: PlanValidationCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Job:
    run = owned_research_run(run_id, user, db)
    executor = executor_by_id(payload.executor)
    if executor is None:
        raise HTTPException(status_code=422, detail="Unknown execution backend")
    if not executor.available:
        raise HTTPException(status_code=409, detail=f"{executor.label} is not configured or available")
    plan = db.scalar(select(ExperimentPlan).where(ExperimentPlan.research_run_id == run.id))
    if plan is None:
        raise HTTPException(status_code=409, detail="Finish a real literature proposal before validating its execution hand-off")
    active = db.scalar(select(Job).where(Job.research_run_id == run.id, Job.kind == "plan-validation", Job.status.in_([JobStatus.QUEUED, JobStatus.ASSIGNED, JobStatus.RUNNING])))
    if active:
        return active
    job = Job(research_run_id=run.id, kind="plan-validation", status=JobStatus.QUEUED, payload={"executor": executor.id, "evidence_mode": executor.evidence_mode, "plan_id": str(plan.id)})
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@app.get("/research", response_model=list[ResearchResponse])
def list_research(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ResearchRun]:
    return list(db.scalars(
        select(ResearchRun).join(Project).where(Project.owner_id == user.id).order_by(ResearchRun.created_at.desc())
    ))


@app.get("/research/{run_id}", response_model=ResearchResponse)
def get_research(run_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ResearchRun:
    run = db.scalar(select(ResearchRun).join(Project).where(ResearchRun.id == run_id, Project.owner_id == user.id))
    if run is None:
        raise HTTPException(status_code=404, detail="Research run not found")
    return run


def owned_research_run(run_id: UUID, user: User, db: Session) -> ResearchRun:
    run = db.scalar(select(ResearchRun).join(Project).where(ResearchRun.id == run_id, Project.owner_id == user.id))
    if run is None:
        raise HTTPException(status_code=404, detail="Research run not found")
    return run


@app.get("/research/{run_id}/papers", response_model=list[PaperResponse])
def research_papers(run_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Paper]:
    owned_research_run(run_id, user, db)
    query = select(Paper).join(ResearchPaper).where(ResearchPaper.research_run_id == run_id).order_by(ResearchPaper.rank.asc())
    return list(db.scalars(query))


@app.get("/research/{run_id}/progress", response_model=list[ResearchEventResponse])
def research_progress(run_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ResearchEvent]:
    owned_research_run(run_id, user, db)
    return list(db.scalars(select(ResearchEvent).where(ResearchEvent.research_run_id == run_id).order_by(ResearchEvent.created_at.asc())))


@app.get("/research/{run_id}/proposal")
def research_proposal(run_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    owned_research_run(run_id, user, db)
    hypothesis = db.scalar(select(Hypothesis).where(Hypothesis.research_run_id == run_id).order_by(Hypothesis.created_at.desc()))
    plan = db.scalar(select(ExperimentPlan).where(ExperimentPlan.research_run_id == run_id).order_by(ExperimentPlan.created_at.desc()))
    return {"hypothesis": {"statement": hypothesis.statement, "rationale": hypothesis.rationale, "risk": hypothesis.risk} if hypothesis else None, "experiment_plan": {"configuration": plan.configuration, "datasets": plan.datasets, "metrics": plan.metrics, "resource_estimate": plan.resource_estimate, "experiment_design": (plan.configuration or {}).get("experiment_design")} if plan else None}


@app.get("/research/{run_id}/synthesis")
def research_synthesis(run_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    owned_research_run(run_id, user, db)
    knowledge = db.scalar(
        select(Knowledge).where(Knowledge.research_run_id == run_id, Knowledge.paper_id.is_(None)).order_by(Knowledge.created_at.desc())
    )
    return knowledge.extracted if knowledge else {"summary": "Literature synthesis is pending worker completion.", "evidence_excerpts": []}


@app.get("/jobs", response_model=list[JobResponse])
def list_jobs(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Job]:
    return list(db.scalars(
        select(Job).join(ResearchRun, Job.research_run_id == ResearchRun.id).join(Project).where(Project.owner_id == user.id)
        .order_by(Job.created_at.desc())
    ))


@app.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Job:
    job = db.scalar(
        select(Job).join(ResearchRun, Job.research_run_id == ResearchRun.id).join(Project)
        .where(Job.id == job_id, Project.owner_id == user.id)
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/jobs/{job_id}/events", response_model=list[JobEventResponse])
def get_job_events(job_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[JobEvent]:
    permitted_job = db.scalar(
        select(Job.id).join(ResearchRun, Job.research_run_id == ResearchRun.id).join(Project)
        .where(Job.id == job_id, Project.owner_id == user.id)
    )
    if permitted_job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return list(db.scalars(select(JobEvent).where(JobEvent.job_id == job_id).order_by(JobEvent.created_at.asc())))


@app.post("/jobs/{job_id}/cancel", response_model=JobResponse)
def cancel_job(job_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Job:
    job = db.scalar(
        select(Job).join(ResearchRun, Job.research_run_id == ResearchRun.id).join(Project)
        .where(Job.id == job_id, Project.owner_id == user.id)
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status in {JobStatus.QUEUED, JobStatus.ASSIGNED}:
        record_event(db, job, JobStatus.CANCELLED, "Cancelled by the user before worker execution")
        return job
    is_dmlf = job.kind == "plan-validation" and job.payload.get("executor") == "dmlf"
    remote_job_id = job.payload.get("remote_job_id") if is_dmlf else None
    if job.status != JobStatus.RUNNING or not remote_job_id:
        raise HTTPException(status_code=409, detail=f"Cannot cancel a {job.status.value} job")
    try:
        cancel_dmlf(str(remote_job_id))
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=f"Could not cancel DMLF job {remote_job_id}: {error}") from error
    record_event(db, job, JobStatus.CANCELLED, f"Cancellation requested for DMLF job {remote_job_id}")
    return job


@app.get("/workers", response_model=list[WorkerResponse])
def list_workers(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Worker]:
    """Live worker registry; hardware-aware scheduling is added in Milestone 2."""
    return list(db.scalars(select(Worker).order_by(Worker.last_heartbeat_at.desc().nullslast())))


@app.get("/queue")
def queue_summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, int]:
    query = select(Job.status, func.count(Job.id)).join(ResearchRun, Job.research_run_id == ResearchRun.id).join(Project)
    query = query.where(Project.owner_id == user.id).group_by(Job.status)
    counts = {status.value: count for status, count in db.execute(query)}
    return {status.value: int(counts.get(status.value, 0)) for status in JobStatus}


@app.get("/reports", response_model=list[ReportResponse])
def list_reports(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Report]:
    query = select(Report).join(ResearchRun).join(Project).where(Project.owner_id == user.id).order_by(Report.created_at.desc())
    return list(db.scalars(query))


@app.get("/artifacts/{artifact_id}/content")
def get_artifact_content(artifact_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> StreamingResponse:
    artifact = db.scalar(
        select(Artifact).join(Job).join(ResearchRun).join(Project)
        .where(Artifact.id == artifact_id, Project.owner_id == user.id)
    )
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    try:
        result = get_artifact(artifact.storage_key)
    except Exception as error:
        raise HTTPException(status_code=502, detail="Artifact storage is unavailable") from error
    filename = artifact.storage_key.rsplit("/", 1)[-1]
    return StreamingResponse(
        result["Body"].iter_chunks(),
        media_type=artifact.media_type,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
