# Refresh the dashboard data from BigQuery and publish it to the private Cloud Run site.
# Run from this folder:  powershell -ExecutionPolicy Bypass -File .\publish.ps1
# Needs: Node, and gcloud signed in with access to profound-keel-500007-s4.
$ErrorActionPreference = 'Stop'
$project = 'profound-keel-500007-s4'
$region = 'asia-southeast1'
Set-Location $PSScriptRoot

npm run sources
if ($LASTEXITCODE -ne 0) { throw 'Query refresh failed' }
npm run build
if ($LASTEXITCODE -ne 0) { throw 'Site build failed' }

$build = gcloud builds submit --config cloudbuild.dashboard.yaml --region=$region --format='value(id)' .
if ($LASTEXITCODE -ne 0) { throw 'Image build failed' }
$id = ($build | Select-Object -Last 1).Trim()

gcloud run deploy cp2-dashboard --region=$region --project=$project `
  --image="$region-docker.pkg.dev/$project/cp2-reporting/dashboard:$id"
if ($LASTEXITCODE -ne 0) { throw 'Deploy failed' }
gcloud run services update-traffic cp2-dashboard --region=$region --project=$project --to-latest
Write-Host "Published image $id to https://cp2-dashboard-964813222593.asia-southeast1.run.app"
