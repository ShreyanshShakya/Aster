"""Milestone 1 scheduler: publishes durable queued jobs to the local worker queue."""
import time

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Job, JobStatus
from app.queue import enqueue_job
from app.services import record_event


def tick() -> int:
    with SessionLocal() as db:
        jobs = list(db.scalars(select(Job).where(Job.status == JobStatus.QUEUED)))
        for job in jobs:
            record_event(db, job, JobStatus.ASSIGNED, "Published to the local worker queue")
            enqueue_job(job.id)
        return len(jobs)


def main() -> None:
    while True:
        try:
            tick()
        except Exception as error:
            print(f"scheduler error: {error}", flush=True)
        time.sleep(1)


if __name__ == "__main__":
    main()
