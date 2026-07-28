# Architecture

```text
Next.js dashboard
  | REST + authenticated WebSocket
FastAPI API
  | PostgreSQL (durable truth)
  | Redis (queue + live events)
  | MinIO (reports and artifacts)
Scheduler -> allowlisted executor -> local worker
```

## Service responsibilities

| Service | Responsibility |
| --- | --- |
| `frontend` | Browser UI, session-scoped JWT, REST calls, job-event WebSocket |
| `backend` | Authentication, ownership checks, research/job APIs, artifact proxy |
| `postgres` | Users, projects, research runs, jobs, events, reports, artifacts, workers |
| `redis` | Short-lived work queue and per-user live-event channels |
| `scheduler` | Converts durable `queued` jobs into Redis work items |
| `worker` | Claims only allowlisted dummy-research jobs and emits durable status events |
| `minio` | Markdown and JSON report bodies; credentials never reach the browser |

## Execution contract

The execution contract is intentionally narrow:

```text
Research plan -> selected executor -> job spec -> lifecycle events -> structured result -> artifact keys
```

The local executor validates the plan-to-worker hand-off and labels its result as simulated; it never invents benchmark metrics. The DMLF executor is available only when its configured async bridge passes a health check. It preserves this contract and never exposes arbitrary agent-generated shell commands.

The optional `docker-compose.dmlf.yml` extension runs a DMLF manager, bridge, and two CPU agents on the same Compose network. The platform backend then addresses the bridge as `http://dmlf-bridge:8002`; no host-network address is needed for that bundled demo. The dashboard enables DMLF only after the bridge is healthy and at least the requested number of agents are registered.

## State ownership

PostgreSQL is authoritative. Redis may be cleared or replayed without losing a completed report, job history, or audit timeline. MinIO is artifact storage; its object keys are recorded in PostgreSQL.
