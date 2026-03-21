# Backend

The backend is a FastAPI application that handles:

- User authentication
- Gmail and Outlook account linking
- Webhook ingestion and normalization
- Commitment extraction and storage
- Dashboard APIs consumed by the frontend

## Key Folders

```text
backend/
├── app/
│   ├── agents/       LangGraph extraction pipeline
│   ├── core/         Config and logging
│   ├── db/           Database session setup
│   ├── middleware/   Auth middleware
│   ├── routes/       FastAPI route modules
│   └── services/     OAuth, ingestion, LLM, storage, reconciliation
├── migrations/       SQL migrations
├── worker/           Redis stream workers
└── scheduler/        Background scheduler
```

## Entrypoints

- API app: `app.main:app`
- Worker: `python -m worker.main normalizer|extractor`
- Scheduler: `python -m scheduler.main`

## Local Run

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
