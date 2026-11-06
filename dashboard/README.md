# Nomobug management dashboard (Evidence)

Open-source [Evidence](https://evidence.dev) site on the BigQuery `predictions` and `gold` datasets.

- Live (Google sign-in, same people as the portal): https://cp2-dashboard-964813222593.asia-southeast1.run.app
- Pages: `pages/*.md` (Overview, Service follow-up, Bookings & staffing, Sales & areas, Payments)
- Queries: `sources/nomobug/*.sql`; colours: `evidence.config.yaml` (website palette)

## Run locally

```
npm install
npm run sources
npm run dev
```

## Publish fresh data

```
powershell -ExecutionPolicy Bypass -File .\publish.ps1
```

Refreshes the queries, builds the static site, builds the image in Cloud Build and deploys `cp2-dashboard`.

## Privacy

The built site contains the customer call list. It is served only behind Google IAP:
the service allows `run.invoker` for the IAP service agent only, and IAP access matches `cp2-portal`.
The runtime account `cp2-dashboard-runtime` has no permissions. Never make it public.
Built files and query extracts are excluded from git (`.gitignore`).
