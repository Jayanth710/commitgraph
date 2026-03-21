# Frontend

The frontend is a Next.js App Router application for CommitGraph.

## Main Areas

- `src/app/`: Route pages
- `src/components/`: Shared UI and layout components
- `src/lib/`: API client, auth helpers, utilities
- `public/`: Static assets

## Main Screens

- Dashboard
- Commitments
- Review Queue
- Timeline
- People
- Calendar
- Settings

## Development

```bash
npm install
npm run dev
```

The app expects `NEXT_PUBLIC_API_URL` to point at the backend API.

Default local API URL:

```text
http://localhost:8000
```

## Deployment

The production deployment is handled by the GitHub Actions workflow at:

- `../.github/workflows/deploy-frontend.yml`

That workflow builds and deploys the frontend through Vercel.
