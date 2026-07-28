# Database

Migrations are managed by Alembic in `backend/alembic/versions`. The backend runs `alembic upgrade head` before accepting traffic.

| Table | Purpose |
| --- | --- |
| `users` | Local account identity and password hash |
| `projects` | User-owned research workspaces |
| `research_runs` | Question, plan, and research status |
| `jobs` | Executable work for a research run |
| `job_events` | Immutable lifecycle/audit timeline |
| `workers` | Registered local or future remote workers |
| `artifacts` | MinIO object references and media types |
| `reports` | Links a research run to Markdown and JSON artifacts |

## Rules

- Store credentials and object bodies outside the database.
- Store artifact metadata and object keys in the database.
- Verify project ownership for every user-facing job, report, and artifact endpoint.
- Treat Redis as transient transport, never as the job-system source of truth.
