# Nomobug management dashboard (Evidence)

Open-source [Evidence](https://evidence.dev) site on the BigQuery `predictions` and `gold` datasets.

- Live (Google sign-in, same people as the portal): https://cp2-dashboard-964813222593.asia-southeast1.run.app
- Pages: `pages/*.md` (Overview, Service follow-up, Bookings & staffing, Sales & customers, Maps & patterns, Services & warranty, Payments)
- Queries: `sources/nomobug/*.sql`; colours: `evidence.config.yaml` (website palette)

## Run locally

```
npm install
npm run sources
npm run dev
```

## How the live site updates

- Every day at 06:45 Malaysia time, Cloud Scheduler `cp2-dashboard-refresh-daily` runs the Cloud Run job
  `cp2-dashboard-refresh` (image built from `refresh/`): it runs the queries, builds the site and uploads it to
  `gs://profound-keel-500007-s4-cp2-dashboard/site/`, removing files from the previous build.
- The `cp2-dashboard` service is nginx only (`refresh/Dockerfile.serve`) with that bucket folder mounted read-only,
  so new data appears without a redeploy.
- Refresh now: `powershell -ExecutionPolicy Bypass -File .\publish.ps1`
- After changing pages or queries, rebuild the job image:
  `gcloud builds submit --config refresh/cloudbuild.yaml --ignore-file=refresh/.gcloudignore --region=asia-southeast1 .`
  then `gcloud run jobs update cp2-dashboard-refresh --region=asia-southeast1 --image=<new image>`.

Accounts: `cp2-dashboard-refresh` (BigQuery read, job user, write to the dashboard bucket, may start its own job);
`cp2-dashboard-runtime` (read the dashboard bucket only).

## Privacy

The built site contains the customer call list. It is served only behind Google IAP:
the service allows `run.invoker` for the IAP service agent only, and IAP access matches `cp2-portal`.
The runtime account `cp2-dashboard-runtime` has no permissions. Never make it public.
Built files and query extracts are excluded from git (`.gitignore`).
