<#
.SYNOPSIS
Create the 06:00 MYT Cloud Scheduler trigger after a successful manual run.
.DESCRIPTION
The schedule has no retries and is paused by default. Use -Apply -Activate
after a successful manual execution and spend/permissions review.
#>
param([switch]$Apply, [switch]$Activate)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Project = 'profound-keel-500007-s4'
$Region = 'asia-southeast1'
$Job = 'cp2-reporting-daily'
$Scheduler = 'cp2-reporting-daily-trigger'
$Identity = "cp2-reporting-scheduler@$Project.iam.gserviceaccount.com"
$Uri = "https://run.googleapis.com/v2/projects/$Project/locations/$Region/jobs/${Job}:run"

if (-not $Apply) {
    Write-Output 'Dry-run: 06:00 Asia/Kuala_Lumpur, POST Cloud Run jobs.run, OAuth scheduler identity, zero retries. No changes made.'
    return
}
& gcloud run jobs describe $Job --project $Project --region $Region --quiet --format='value(metadata.name)' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Cloud Run job does not exist; deploy and test it first' }
& gcloud run jobs add-iam-policy-binding $Job --project $Project --region $Region `
    --member "serviceAccount:$Identity" --role roles/run.invoker --quiet | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Could not bind scheduler invoker to the job' }

$common = @('--project',$Project,'--location',$Region,'--schedule','0 6 * * *',
    '--time-zone','Asia/Kuala_Lumpur','--uri',$Uri,'--http-method','POST',
    '--oauth-service-account-email',$Identity,'--oauth-token-scope','https://www.googleapis.com/auth/cloud-platform',
    '--max-retry-attempts','0','--max-retry-duration','0s','--attempt-deadline','30s',
    '--message-body','{}','--headers','Content-Type=application/json','--quiet')
& gcloud scheduler jobs describe $Scheduler --project $Project --location $Region --quiet --format='value(name)' 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) {
    & gcloud scheduler jobs update http $Scheduler @common
} else {
    & gcloud scheduler jobs create http $Scheduler @common
}
if ($LASTEXITCODE -ne 0) { throw 'Scheduler create/update failed' }
if ($Activate) {
    & gcloud scheduler jobs resume $Scheduler --project $Project --location $Region --quiet
    if ($LASTEXITCODE -ne 0) { throw 'Scheduler resume failed' }
    Write-Output 'Daily 06:00 MYT schedule active.'
} else {
    & gcloud scheduler jobs pause $Scheduler --project $Project --location $Region --quiet
    if ($LASTEXITCODE -ne 0) { throw 'Scheduler pause failed' }
    Write-Output 'Schedule exists but is paused pending manual release verification.'
}
