import json
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Artifact, ExperimentPlan, Job, JobEvent, JobStatus, Project, Report, ResearchEvent, ResearchRun
from app.queue import publish_event, publish_user_event
from app.research import build_mock_plan, render_mock_report
from app.storage import put_text


def record_event(db: Session, job: Job, status: JobStatus, message: str) -> None:
    job.status = status
    db.add(JobEvent(job_id=job.id, status=status, message=message))
    db.commit()
    event = {"job_id": str(job.id), "status": status.value, "message": message}
    publish_event(job.id, event)
    owner_id = db.scalar(
        select(Project.owner_id).join(ResearchRun, ResearchRun.project_id == Project.id).where(ResearchRun.id == job.research_run_id)
    )
    if owner_id:
        publish_user_event(owner_id, event)


def complete_dummy_research(db: Session, job: Job) -> None:
    run = db.get(ResearchRun, job.research_run_id)
    if run is None:
        raise RuntimeError("Research run was not found")
    plan = build_mock_plan(run)
    run.plan = plan
    run.status = JobStatus.SUCCEEDED
    report_markdown = render_mock_report(run, plan)
    prefix = f"runs/{run.id}"
    markdown_key = put_text(f"{prefix}/report.md", report_markdown, "text/markdown")
    json_key = put_text(f"{prefix}/report.json", json.dumps(plan, indent=2), "application/json")
    markdown_artifact = Artifact(job_id=job.id, storage_key=markdown_key, media_type="text/markdown")
    json_artifact = Artifact(job_id=job.id, storage_key=json_key, media_type="application/json")
    db.add_all([markdown_artifact, json_artifact])
    db.flush()
    db.add(Report(research_run_id=run.id, markdown_artifact_id=markdown_artifact.id, json_artifact_id=json_artifact.id))
    job.result = {"report_markdown": markdown_key, "report_json": json_key, "completed_at": datetime.now(timezone.utc).isoformat()}
    db.commit()


def complete_plan_validation(db: Session, job: Job) -> None:
    """Record a safe local validation hand-off; it never fabricates a benchmark metric."""
    run = db.get(ResearchRun, job.research_run_id)
    if run is None:
        raise RuntimeError("Research run was not found")
    plan = db.scalar(select(ExperimentPlan).where(ExperimentPlan.research_run_id == run.id).order_by(ExperimentPlan.created_at.desc()))
    if plan is None:
        raise RuntimeError("A completed research proposal is required before local validation")
    design = (plan.configuration or {}).get("experiment_design", {})
    validation = {
        "mode": "local-plan-validation",
        "evidence": "simulated-execution-contract",
        "status": "validated-for-execution-adapter",
        "question": run.question,
        "baseline": design.get("baseline", {}).get("name"),
        "intervention": design.get("intervention", {}).get("name"),
        "primary_metric": design.get("primary_metric"),
        "metric_value": None,
        "note": "No model training or benchmark evaluation was performed. This result validates only the platform's plan-to-worker hand-off.",
        "validated_at": datetime.now(timezone.utc).isoformat(),
    }
    prefix = f"runs/{run.id}/local-validation/{job.id}"
    markdown = "# Local execution validation\n\n" + "\n".join(
        [f"- **{key.replace('_', ' ')}:** {value}" for key, value in validation.items()]
    )
    markdown_artifact = Artifact(job_id=job.id, storage_key=put_text(f"{prefix}/validation.md", markdown, "text/markdown"), media_type="text/markdown")
    json_artifact = Artifact(job_id=job.id, storage_key=put_text(f"{prefix}/validation.json", json.dumps(validation, indent=2), "application/json"), media_type="application/json")
    db.add_all([markdown_artifact, json_artifact])
    db.flush()
    db.add(Report(research_run_id=run.id, markdown_artifact_id=markdown_artifact.id, json_artifact_id=json_artifact.id))
    db.add(ResearchEvent(research_run_id=run.id, stage="execution-validation", message="Validated plan-to-worker hand-off; no training metrics were generated", data=validation))
    job.result = validation
    db.commit()


def store_dmlf_result(db: Session, job: Job, remote_job_id: str, result: dict) -> None:
    """Persist the manager-owned DMLF result as an auditable JSON artifact."""
    run = db.get(ResearchRun, job.research_run_id)
    if run is None:
        raise RuntimeError("Research run was not found")
    payload = {"mode": "dmlf", "remote_job_id": remote_job_id, "result": result, "evidence": "real-training-result-from-dmlf-bridge"}
    key = put_text(f"runs/{run.id}/dmlf/{remote_job_id}/result.json", json.dumps(payload, indent=2), "application/json")
    artifact = Artifact(job_id=job.id, storage_key=key, media_type="application/json")
    db.add(artifact)
    db.flush()
    db.add(Report(research_run_id=run.id, json_artifact_id=artifact.id))
    job.result = payload
    db.add(ResearchEvent(research_run_id=run.id, stage="dmlf-result", message="DMLF returned a terminal result", data=payload))
    db.commit()
