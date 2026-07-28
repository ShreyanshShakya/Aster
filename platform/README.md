# Aster Platform — Milestone 1

This directory is the production-style successor to the existing Aster hackathon MVP. It is deliberately separate while the migration is in progress.

## Start locally

```powershell
cd platform
Copy-Item .env.example .env
docker compose up --build
```

- Dashboard: http://localhost:3001
- API docs: http://localhost:8000/docs
- MinIO console: http://localhost:9001

Create an account or sign in directly in the dashboard, then create a project and submit a question. The JWT is retained only for the active browser session. The scheduler dispatches an allowlisted `dummy-research` job, the worker stores Markdown and JSON reports in MinIO, and the job state is persisted in PostgreSQL. The dashboard opens an authenticated WebSocket and refreshes job state as the scheduler and worker emit events.

Completed reports are listed in the dashboard. Their content is proxied through authenticated artifact endpoints, so the browser never receives MinIO access credentials.

The API container runs `alembic upgrade head` before it accepts traffic. Versioned schema changes belong in `backend/alembic/versions/`; application startup does not create tables directly.

## Architecture boundary

The local worker is the first implementation of the platform worker contract. The optional DMLF adapter uses the same lifecycle and artifact interfaces rather than exposing raw shell execution to agents.

## Optional DMLF executor

The dashboard exposes DMLF only when both values below are set and the DMLF HTTP bridge is already running. A DMLF run submits a bounded experiment, polls the bridge's durable job state, and stores the returned result as a JSON artifact.

For the bundled, containerized two-agent CPU demo, use the DMLF Compose override. It sets the required backend environment values automatically:

```powershell
docker compose -f docker-compose.yml -f docker-compose.dmlf.yml up --build
```

It starts the base platform plus `dmlf-manager`, `dmlf-bridge`, and two DMLF CPU agents. In the dashboard, wait for **DMLF distributed training** to become available before queueing it; Aster waits for the bridge health check and both registered agents.

Once DMLF has accepted a running job, its **Cancel** action is forwarded to the bridge and then to the DMLF manager. Aster records the request as a durable cancellation event; it does not relabel it as a training failure.

For an externally managed DMLF cluster instead, configure:

```text
DMLF_ADAPTER_ENABLED=true
DMLF_BRIDGE_ENDPOINT=http://host.docker.internal:8002
DMLF_REQUESTED_NODES=1
```

For a stack started outside Docker on the same machine, use `http://127.0.0.1:8002` instead. Do not enable this executor until the manager, node agents, and bridge have been validated separately.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [API](docs/API.md)
- [Database](docs/DATABASE.md)
- [Roadmap](docs/ROADMAP.md)
- [Contributing](docs/CONTRIBUTING.md)

## End-to-end smoke test

After starting the stack, run this from the `platform` directory:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\smoke-test.ps1
```

The script creates an isolated account and project, waits for the local worker to complete a mock research run, verifies durable lifecycle events, then retrieves the generated Markdown report through the authenticated artifact API. No email is sent by the local platform.
