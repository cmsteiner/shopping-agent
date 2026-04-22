# Web Deployment

## Overview

The v1 web app is deployed as part of the existing FastAPI service.

- FastAPI serves the API, SMS webhook, cron endpoint, and the web UI shell.
- The shared-link entrypoint is `/app/<WEB_SHARED_TOKEN>`.
- Built frontend assets are served from `/web-static/...`.

## Railway Configuration

The Railway service now uses config-as-code in [railway.toml](C:/Users/Chris/Documents/shopping-agent/railway.toml) to build the frontend before startup.

Build step:

```toml
[build]
buildCommand = "cd frontend && npm ci && npm run build"
```

Start step:

```toml
[deploy]
startCommand = "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/health"
```

This follows Railway's current config-as-code support for build and start command overrides:
- [Config as Code](https://docs.railway.com/config-as-code/reference)
- [Build and Start Commands](https://docs.railway.com/builds/build-and-start-commands)

## Required Environment Variables

- `WEB_SHARED_TOKEN`
- `WEBHOOK_SECRET`
- `DATABASE_URL`
- `CHRIS_PHONE`
- `DONNA_PHONE`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_PHONE_NUMBER`
- `ANTHROPIC_API_KEY`

## Local Verification

Run backend tests:

```bash
.venv311\Scripts\python.exe -m pytest app/tests/test_api.py app/tests/test_web_app.py
```

Run frontend tests:

```bash
cd frontend
npm test
```

Run a production frontend build:

```bash
cd frontend
npm run build
```

After the frontend build exists in `frontend/dist`, start the app and open:

```text
/app/<WEB_SHARED_TOKEN>
```

## Deploy Smoke Checklist

- `GET /health` returns `200`
- `GET /app/<WEB_SHARED_TOKEN>` returns the SPA shell
- `GET /api/app-state` works with `X-App-Token`
- item add/edit/delete works from the web UI
- trip start and finish work from the web UI
- category create/rename/delete works from the web UI
- duplicate and conflict flows resolve correctly
