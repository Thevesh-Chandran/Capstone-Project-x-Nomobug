# Nomobug management dashboard (Evidence)

Open-source [Evidence](https://evidence.dev) site on the BigQuery `predictions` and `gold` datasets.

- Shown inside the staff website (one address, one menu): each website page opens with its dashboard section and has its actions below. Served by the website at `/dashboard`, built with `deployment.basePath: /dashboard`.
- Website: https://cp2-portal-964813222593.asia-southeast1.run.app
- Pages: `pages/*.md` (Overview, Service follow-up, Bookings & staffing, Sales & customers, Maps & patterns, Services & warranty, Payments). Each page has its own filters.
- Model test figures come from `predictions.model_evaluation`, published by the daily reporting job; no figures are typed into the pages.
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
- The website (`cp2-portal`) mounts that bucket folder read-only at `/mnt/dashboard` (`CP2_DASHBOARD_DIR`) and serves it at `/dashboard`
  to signed-in users only, so new data appears without a redeploy.
- Refresh now: `powershell -ExecutionPolicy Bypass -File .\publish.ps1`
- After changing pages or queries, rebuild the job image:
  `gcloud builds submit --config refresh/cloudbuild.yaml --ignore-file=refresh/.gcloudignore --region=asia-southeast1 .`
  then `gcloud run jobs update cp2-dashboard-refresh --region=asia-southeast1 --image=<new image>`.

Accounts: `cp2-dashboard-refresh` (BigQuery read, job user, write to the dashboard bucket, may start its own job);
`cp2-portal-runtime` (read the dashboard bucket). The separate `cp2-dashboard` nginx service was deleted on 6 November 2026;
`refresh/Dockerfile.serve` and `nginx.conf` are kept only as history.

## Privacy

The built site holds aggregate business figures and risk scores, but no customer names or contact details
(the call list is shown by the website itself). It is still served only to signed-in users: the website checks
the Google IAP assertion before returning any `/dashboard` file. Never make the bucket or the site public.
Built files and query extracts are excluded from git (`.gitignore`).
