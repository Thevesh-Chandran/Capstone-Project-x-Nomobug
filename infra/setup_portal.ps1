param([switch]$Apply)
$ErrorActionPreference = 'Stop'
$projectId = 'profound-keel-500007-s4'
$bucketName = 'cp2-portal-profound-keel-500007-s4'
$portalIdentity = "cp2-portal-runtime@$projectId.iam.gserviceaccount.com"
$reportingIdentity = "cp2-reporting-job@$projectId.iam.gserviceaccount.com"
function Invoke-Cloud([string[]]$Arguments) {
    & gcloud @Arguments
    if ($LASTEXITCODE -ne 0) { throw 'Cloud setup command failed; inspect the typed error before retrying.' }
}
if (-not $Apply) {
    Write-Output 'Creates private portal/AI identities and a private snapshot bucket. Grants portal read-only bucket access, reporting bucket writes, and portal-secret access. No public access or collector changes.'
    return
}
Invoke-Cloud @('iam','service-accounts','create','cp2-portal-runtime','--project',$projectId,'--display-name','CP2 portal runtime','--quiet')
Invoke-Cloud @('iam','service-accounts','create','cp2-ollama-runtime','--project',$projectId,'--display-name','CP2 private Ollama runtime','--quiet')
Invoke-Cloud @('storage','buckets','create',"gs://$bucketName",'--project',$projectId,'--location','asia-southeast1','--uniform-bucket-level-access','--public-access-prevention','--quiet')
Invoke-Cloud @('storage','buckets','add-iam-policy-binding',"gs://$bucketName",'--member',"serviceAccount:$portalIdentity",'--role','roles/storage.objectViewer','--quiet')
Invoke-Cloud @('storage','buckets','add-iam-policy-binding',"gs://$bucketName",'--member',"serviceAccount:$reportingIdentity",'--role','roles/storage.objectUser','--quiet')
Invoke-Cloud @('secrets','create','cp2-portal-access-code','--project',$projectId,'--data-file','secrets/portal_token.txt','--replication-policy','automatic','--quiet')
Invoke-Cloud @('secrets','add-iam-policy-binding','cp2-portal-access-code','--project',$projectId,'--member',"serviceAccount:$portalIdentity",'--role','roles/secretmanager.secretAccessor','--quiet')
foreach ($name in @('business_snapshot.json','area_evaluation.json','area_rows_private.json','district_boundaries_public.json')) {
    Invoke-Cloud @('storage','cp',"outputs/portal/$name","gs://$bucketName/current/$name",'--quiet')
}
Write-Output 'Private portal resources prepared. No raw customer identities, credentials or model bundles uploaded.'
