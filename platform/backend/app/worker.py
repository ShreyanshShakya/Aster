"""Safe local worker for Milestone 1; it only executes the allowlisted dummy-research job."""
import os
import socket
import time
from datetime import datetime, timezone

from sqlalchemy import select

from app.database import SessionLocal
from app.core.config import get_settings
from app.dmlf_client import status as dmlf_status, submit as submit_dmlf
from app.models import Job, JobStatus, ResearchRun, Worker
from app.queue import pop_job
from app.services import complete_dummy_research, complete_plan_validation, record_event, store_dmlf_result
from app.research_engine import run_research_plan


WORKER_NAME = os.getenv("WORKER_NAME", socket.gethostname())


class DmlfCancelled(Exception):
    """Signals a user-requested DMLF cancellation without treating it as a worker failure."""


def heartbeat(db, worker: Worker) -> None:
    worker.last_heartbeat_at = datetime.now(timezone.utc)
    db.commit()


def get_worker(db) -> Worker:
    worker = db.scalar(select(Worker).where(Worker.name == WORKER_NAME))
    if worker is None:
        worker = Worker(name=WORKER_NAME, capabilities={"executors": ["dummy-research", "research-plan", "local-plan-validation"], "resource": "cpu"})
        db.add(worker)
        db.commit()
    else:
        worker.capabilities = {"executors": ["dummy-research", "research-plan", "local-plan-validation"], "resource": "cpu"}
    heartbeat(db, worker)
    return worker


def dmlf_experiment(run: ResearchRun) -> dict:
    """Translate only the bounded, persisted plan fields into the DMLF allowlist."""
    configuration = (run.plan or {}).get("configuration", {})
    question = run.question.lower()
    settings = get_settings()
    return {
        "id": str(run.id),
        "dataset": "mnist" if "mnist" in question else "synthetic",
        "augmentation": "standard" if "augment" in question else "none",
        "epochs": min(max(int(configuration.get("epochs", 1)), 1), 3),
        "learningRate": float(configuration.get("learning_rate", 0.01)),
        "seed": 42,
        "distributed": {"nodes": settings.dmlf_requested_nodes, "processesPerNode": 1},
    }


def execute_dmlf(db, job: Job, run: ResearchRun) -> None:
    experiment = dmlf_experiment(run)
    submitted = submit_dmlf(experiment)
    remote_job_id = submitted["jobId"]
    job.payload = {**job.payload, "remote_job_id": remote_job_id, "experiment": experiment}
    db.commit()
    record_event(db, job, JobStatus.RUNNING, f"Submitted DMLF job {remote_job_id}; polling bridge")
    deadline = time.monotonic() + get_settings().dmlf_timeout_seconds
    last_state: tuple[str, int] | None = None
    while time.monotonic() < deadline:
        db.refresh(job)
        if job.status == JobStatus.CANCELLED:
            raise DmlfCancelled(f"DMLF job {remote_job_id} was cancelled by the user")
        remote = dmlf_status(remote_job_id)
        remote_status, progress = remote.get("status", "unknown"), int(remote.get("progress", 0))
        state = (remote_status, progress)
        if state != last_state:
            record_event(db, job, JobStatus.RUNNING, f"DMLF {remote_job_id}: {remote_status} ({progress}%)")
            last_state = state
        if remote_status == "completed":
            store_dmlf_result(db, job, remote_job_id, remote)
            return
        if remote_status == "canceled":
            raise DmlfCancelled(remote.get("error") or f"DMLF job {remote_job_id} was canceled")
        if remote_status == "failed":
            raise RuntimeError(remote.get("error") or f"DMLF job {remote_job_id} {remote_status}")
        time.sleep(max(1, get_settings().dmlf_poll_seconds))
    raise RuntimeError(f"DMLF job {remote_job_id} exceeded the configured timeout")


def execute(job_id) -> None:
    with SessionLocal() as db:
        worker = get_worker(db)
        job = db.get(Job, job_id)
        if job is None or job.status not in {JobStatus.ASSIGNED, JobStatus.QUEUED}:
            return
        print(f"worker job={job.id} kind={job.kind} state=starting", flush=True)
        job.worker_id = worker.id
        record_event(db, job, JobStatus.RUNNING, f"Worker {worker.name} started allowlisted dummy research")
        try:
            time.sleep(1)  # observable, controlled placeholder for real execution
            if job.kind == "research-plan":
                run = db.get(ResearchRun, job.research_run_id)
                if run is None:
                    raise RuntimeError("Research run was not found")
                result = run_research_plan(db, run)
                job.result = {"mode": "real-literature-planning", "paper_count": len(result["papers"])}
                db.commit()
                print(f"worker job={job.id} kind=research-plan papers={len(result['papers'])} state=completed", flush=True)
            elif job.kind == "dummy-research":
                complete_dummy_research(db, job)
                print(f"worker job={job.id} kind=dummy-research state=completed", flush=True)
            elif job.kind == "plan-validation":
                run = db.get(ResearchRun, job.research_run_id)
                if run is None:
                    raise RuntimeError("Research run was not found")
                if job.payload.get("executor") == "local-plan-validation":
                    complete_plan_validation(db, job)
                elif job.payload.get("executor") == "dmlf":
                    execute_dmlf(db, job, run)
                else:
                    raise RuntimeError("This worker received an unsupported execution backend")
                print(f"worker job={job.id} kind=plan-validation executor={job.payload.get('executor')} state=completed", flush=True)
            else:
                raise RuntimeError(f"Unsupported worker job kind: {job.kind}")
            record_event(db, job, JobStatus.SUCCEEDED, "Worker completed; result artifacts stored in MinIO")
        except DmlfCancelled as cancellation:
            print(f"worker job={job.id} kind={job.kind} state=cancelled detail={cancellation}", flush=True)
            # The API records the durable cancellation event before signaling the bridge.
            if job.status != JobStatus.CANCELLED:
                record_event(db, job, JobStatus.CANCELLED, str(cancellation))
        except Exception as error:
            job.error = str(error)
            if job.kind == "research-plan" and job.research_run_id:
                run = db.get(ResearchRun, job.research_run_id)
                if run is not None:
                    run.status = JobStatus.FAILED
            print(f"worker job={job.id} kind={job.kind} state=failed error={error}", flush=True)
            record_event(db, job, JobStatus.FAILED, f"Worker failed: {error}")


def main() -> None:
    while True:
        try:
            with SessionLocal() as db:
                get_worker(db)
            job_id = pop_job(timeout_seconds=5)
            if job_id:
                execute(job_id)
        except Exception as error:
            print(f"worker error: {error}", flush=True)
            time.sleep(2)


if __name__ == "__main__":
    main()
