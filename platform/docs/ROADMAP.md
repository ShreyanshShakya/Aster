# Roadmap

## Milestone 1 — local platform

- [x] Compose stack: frontend, API, PostgreSQL, Redis, MinIO, scheduler, worker
- [x] JWT signup/login and browser session
- [x] Projects, research runs, jobs, reports, and worker registry
- [x] Mock research plan and MinIO report artifacts
- [x] Scheduler/worker lifecycle, WebSocket updates, durable timeline, queue cancellation
- [x] Repeatable Compose end-to-end smoke test
- [ ] CI runner for the smoke test and backend unit tests

## Milestone 2 — real research execution

- [x] Real literature metadata retrieval, ranking, provenance, and conservative abstract synthesis.
- [x] Persisted hypothesis, experiment design, datasets, metrics, reports, and evidence limits.
- [x] Allowlisted local plan-validation executor and artifacts; simulated results are explicitly labeled.
- [x] DMLF adapter contract: bounded submission, remote job ID, polling, lifecycle events, and JSON result artifacts.
- Add resource-aware worker capabilities and scheduler matching.
- Add real experiment manifests, dataset identifiers, checkpoints, and metrics.

## Milestone 3 — resilient distributed platform

- Worker leases, retry policies, and failed-worker recovery.
- GPU/utilization-aware scheduling and estimated completion time.
- Multi-node deployment profiles and object-storage checkpoint resume.
