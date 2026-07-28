# API

All endpoints except health and authentication require `Authorization: Bearer <JWT>`.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Service health check |
| `POST` | `/auth/signup` | Create local user and return JWT |
| `POST` | `/auth/login` | Return JWT for existing user |
| `GET/PATCH` | `/profile` | Read or rename current user |
| `POST/GET` | `/projects` | Create and list owned projects |
| `POST/GET` | `/research` | Queue and list research runs |
| `GET` | `/jobs` | List owned jobs |
| `GET` | `/jobs/{id}` | Read one owned job |
| `GET` | `/jobs/{id}/events` | Durable scheduler/worker timeline |
| `POST` | `/jobs/{id}/cancel` | Cancel a queued or assigned job |
| `GET` | `/workers` | Worker registry and latest heartbeat |
| `GET` | `/queue` | Current user’s job counts by status |
| `GET` | `/reports` | Completed report metadata |
| `GET` | `/artifacts/{id}/content` | Authenticated artifact streaming proxy |
| `WS` | `/ws/jobs?token=<JWT>` | User-scoped job lifecycle events |

## Lifecycle

```text
queued -> assigned -> running -> succeeded
                   -> cancelled
                   -> failed
```

Only queued and assigned jobs are currently cancellable. Running cancellation is reserved for the DMLF worker adapter, which will have a real process/job identifier to stop.
