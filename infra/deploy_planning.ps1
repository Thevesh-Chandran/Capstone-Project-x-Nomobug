param([Parameter(Mandatory=$true)][string]$Image, [switch]$Activate)
$ErrorActionPreference='Stop'
$projectId='profound-keel-500007-s4'
$regionId='asia-southeast1'
$jobName='cp2-planning-weekly'
$jobIdentity="cp2-planning-job@$projectId.iam.gserviceaccount.com"
$schedulerIdentity="cp2-reporting-scheduler@$projectId.iam.gserviceaccount.com"
$privateBucket="cp2-planning-private-$projectId"
$portalBucket="cp2-portal-$projectId"
function Cloud([string[]]$Arguments){
    & gcloud @Arguments
    if($LASTEXITCODE -ne 0){throw 'Cloud operation failed. Inspect the error before retrying.'}
}
& gcloud iam service-accounts describe $jobIdentity --project $projectId --format='value(email)' 2>$null | Out-Null
if($LASTEXITCODE -ne 0){Cloud @('iam','service-accounts','create','cp2-planning-job','--project',$projectId,'--display-name','CP2 weekly planning forecasts','--quiet')}
& gcloud storage buckets describe "gs://$privateBucket" --project $projectId --format='value(name)' 2>$null | Out-Null
if($LASTEXITCODE -ne 0){Cloud @('storage','buckets','create',"gs://$privateBucket",'--project',$projectId,'--location',$regionId,'--uniform-bucket-level-access','--public-access-prevention','--quiet')}
Cloud @('storage','buckets','add-iam-policy-binding',"gs://$privateBucket",'--member',"serviceAccount:$jobIdentity",'--role','roles/storage.objectUser','--quiet')
foreach($secretName in @('cp2-google-readonly-token','cp2-google-source-metadata')){
    Cloud @('secrets','add-iam-policy-binding',$secretName,'--project',$projectId,'--member',"serviceAccount:$jobIdentity",'--role','roles/secretmanager.secretAccessor','--quiet')
}
$condition="expression=resource.name == 'projects/_/buckets/$portalBucket/objects/current/planning_forecast.json',title=planning-aggregate-only"
Cloud @('storage','buckets','add-iam-policy-binding',"gs://$portalBucket",'--member',"serviceAccount:$jobIdentity",'--role','roles/storage.objectUser','--condition',$condition,'--quiet')
$environment="CP2_PLANNING_GCS_URI=gs://$privateBucket/v1,CP2_PORTAL_GCS_URI=gs://$portalBucket/current,NOMOBUG_GOOGLE_TOKEN=/secrets/google/token.json,NOMOBUG_GOOGLE_METADATA=/secrets/metadata/source.json"
$mounts='/secrets/google/token.json=cp2-google-readonly-token:latest,/secrets/metadata/source.json=cp2-google-source-metadata:latest'
Cloud @('run','jobs','deploy',$jobName,'--project',$projectId,'--region',$regionId,'--image',$Image,'--service-account',$jobIdentity,'--command','python','--args=-m,scripts.cp2_planning_job','--set-env-vars',$environment,'--set-secrets',$mounts,'--tasks','1','--parallelism','1','--max-retries','0','--task-timeout','1200s','--memory','2Gi','--cpu','1','--quiet')
Cloud @('run','jobs','execute',$jobName,'--project',$projectId,'--region',$regionId,'--args=-m,scripts.cp2_planning_job,--check','--wait','--quiet')
Cloud @('run','jobs','add-iam-policy-binding',$jobName,'--project',$projectId,'--region',$regionId,'--member',"serviceAccount:$schedulerIdentity",'--role','roles/run.invoker','--quiet')
$triggerName='cp2-planning-weekly-trigger'
$common=@('--project',$projectId,'--location',$regionId,'--schedule','50 23 * * 0','--time-zone','Asia/Kuala_Lumpur','--uri',"https://run.googleapis.com/v2/projects/$projectId/locations/$regionId/jobs/${jobName}:run",'--http-method','POST','--oauth-service-account-email',$schedulerIdentity,'--oauth-token-scope','https://www.googleapis.com/auth/cloud-platform','--max-retry-attempts','0','--max-retry-duration','0s','--attempt-deadline','30s','--message-body','{}','--quiet')
& gcloud scheduler jobs describe $triggerName --project $projectId --location $regionId --format='value(name)' 2>$null | Out-Null
if($LASTEXITCODE -eq 0){Cloud (@('scheduler','jobs','update','http',$triggerName)+$common+@('--update-headers','Content-Type=application/json'))}
else{Cloud (@('scheduler','jobs','create','http',$triggerName)+$common+@('--headers','Content-Type=application/json'))}
if($Activate){
    $triggerState=(& gcloud scheduler jobs describe $triggerName --project $projectId --location $regionId --format='value(state)').Trim()
    if($triggerState -eq 'PAUSED'){Cloud @('scheduler','jobs','resume',$triggerName,'--project',$projectId,'--location',$regionId,'--quiet')}
    Cloud @('scheduler','jobs','run',$triggerName,'--project',$projectId,'--location',$regionId,'--quiet')
    Write-Output 'Weekly Sunday23:50MYT schedule enabled and manually dispatched through Scheduler. Inspect the resulting execution.'
}else{Cloud @('scheduler','jobs','pause',$triggerName,'--project',$projectId,'--location',$regionId,'--quiet')}
