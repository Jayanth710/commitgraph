# CommitGraph

CommitGraph is a full-stack app that ingests email and calendar activity, extracts actionable commitments, and presents them in a dashboard for tracking, review, and follow-up.

## Repository Layout

```text
commitgraph-main/
├── backend/                FastAPI app, workers, scheduler, migrations
│   ├── app/                API routes, services, auth, extraction pipeline
│   ├── migrations/         SQL schema changes
│   ├── worker/             Redis stream workers
│   └── scheduler/          Background scheduler entry point
├── frontend/               Next.js app
├── .github/workflows/      GitHub Actions deploy pipelines
└── docker-compose.yml      Local development stack
```

## Applications

- `backend/`: FastAPI API, OAuth integrations, webhook handlers, extraction pipeline, and Postgres/Redis integration.
- `frontend/`: Next.js dashboard for commitments, review queue, timeline, calendar, settings, and auth flows.

## Deployment

- Backend deploy pipeline: [`.github/workflows/deploy-backend.yml`](./.github/workflows/deploy-backend.yml)
  Deploys the backend container image to Google Cloud Run.
- Frontend deploy pipeline: [`.github/workflows/deploy-frontend.yml`](./.github/workflows/deploy-frontend.yml)
  Builds and deploys the frontend through Vercel.

## Local Development

Use Docker Compose to run the main local stack:

```bash
docker compose up --build
```

Main services:

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- Postgres: `localhost:5432`
- Redis: `localhost:6379`

## Notes

- Keep schema changes in `backend/migrations/` instead of editing older migrations after they have been applied.
- Local/generated folders such as `frontend/node_modules`, `frontend/.next`, and `.vercel` are intentionally ignored.
