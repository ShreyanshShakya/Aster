# Contributing

## Local setup

```powershell
cd platform
Copy-Item .env.example .env
docker compose up --build
```

Keep `.env` local. It contains development credentials and must not be committed.

## Database changes

1. Change the SQLAlchemy model.
2. Create an Alembic revision in `backend/alembic/versions`.
3. Verify an empty volume can migrate with `alembic upgrade head`.
4. Do not add schema creation code to FastAPI startup.

## Worker changes

Workers must accept only typed, allowlisted job specifications. Never accept raw shell commands or model-generated executable text from the API.

## Smoke test

With the Compose stack running, execute:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\smoke-test.ps1
```

This is the baseline regression check for the complete Milestone 1 flow.
