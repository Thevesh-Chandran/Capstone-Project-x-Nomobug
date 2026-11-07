# Refresh the live dashboard now, instead of waiting for the 06:45 daily run.
# Runs the Cloud Run job cp2-dashboard-refresh, which queries BigQuery, builds the site and
# uploads it to the private bucket the dashboard serves from. No redeploy is needed.
# Run from this folder:  powershell -ExecutionPolicy Bypass -File .\publish.ps1
$ErrorActionPreference = 'Stop'
gcloud run jobs execute cp2-dashboard-refresh --region=asia-southeast1 --project=profound-keel-500007-s4 --wait
if ($LASTEXITCODE -ne 0) { throw 'Refresh job failed; see Cloud Run job logs' }
Write-Host 'Dashboard refreshed: https://cp2-portal-fav22krh7q-as.a.run.app/dashboard/'
