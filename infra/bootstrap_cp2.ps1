<#
.SYNOPSIS
Provision bounded CP2 cloud resources after checking the actual Billing report.
.DESCRIPTION
Dry-run by default. -Apply requires a recent, project-scoped MYR spend read from
Billing Reports. No source secrets are uploaded here. Run seed_cp2_secrets.ps1
separately; the deployment workflow can then create the Cloud Run Job.
#>
param(
    [switch]$Apply,
    [Nullable[decimal]]$ObservedProjectSpendMYR,
    [string]$ObservedAtUtc
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Project = 'profound-keel-500007-s4'
$ProjectNumber = '964813222593'
$Region = 'asia-southeast1'
$BillingAccount = '01404B-EEE653-60D604'
$RepoId = '1289685547'
$OwnerId = '53994531'
$JobIdentity = "cp2-reporting-job@$Project.iam.gserviceaccount.com"
$SchedulerIdentity = "cp2-reporting-scheduler@$Project.iam.gserviceaccount.com"
$DeployerIdentity = "cp2-reporting-deployer@$Project.iam.gserviceaccount.com"
$BudgetName = 'CP2 project monthly stop-work alert RM30'
$Secrets = @('cp2-google-readonly-token', 'cp2-google-source-ids', 'cp2-google-source-metadata')

function Invoke-Gcloud([string[]]$Arguments) {
    & gcloud @Arguments | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "gcloud failed: $($Arguments[0..[Math]::Min(2,$Arguments.Length-1)] -join ' ')" }
}
function Test-Gcloud([string[]]$Arguments) {
    & gcloud @Arguments --quiet --format='value(name)' 2>$null | Out-Null
    return $LASTEXITCODE -eq 0
}

$SelectedProject = (& gcloud config get-value project 2>$null).Trim()
if ($SelectedProject -ne $Project) { throw "Active gcloud project is not $Project" }
$Billing = (& gcloud billing projects describe $Project --format=json --quiet | ConvertFrom-Json)
if ($LASTEXITCODE -ne 0 -or -not $Billing.billingEnabled -or
    $Billing.billingAccountName -ne "billingAccounts/$BillingAccount") {
    throw 'Unexpected billing link or billing disabled'
}
$Account = (& gcloud billing accounts describe $BillingAccount --format=json --quiet | ConvertFrom-Json)
if ($LASTEXITCODE -ne 0 -or $Account.currencyCode -ne 'MYR' -or -not $Account.open) {
    throw 'Billing account is not active in MYR'
}

if (-not $Apply) {
    Write-Output 'Dry-run: budget RM30 MYR, three scoped secrets, three service accounts, one Docker repository, numeric-ID GitHub WIF provider. No changes made.'
    Write-Output 'To apply, supply the current project-scoped Billing Reports amount and observation time.'
    return
}
if ($null -eq $ObservedProjectSpendMYR -or [string]::IsNullOrWhiteSpace($ObservedAtUtc)) {
    throw 'Apply requires ObservedProjectSpendMYR and ObservedAtUtc from Billing Reports'
}
$ObservedAt = [DateTimeOffset]::Parse($ObservedAtUtc).ToUniversalTime()
$AgeHours = ([DateTimeOffset]::UtcNow - $ObservedAt).TotalHours
if ($AgeHours -lt 0 -or $AgeHours -gt 48) { throw 'Billing observation must be within 48 hours' }
if ($ObservedProjectSpendMYR -ge 30 -or $ObservedProjectSpendMYR -lt 0) {
    throw 'Stop-work ceiling reached or invalid spend amount'
}
Write-Output "Project spend preflight: RM$ObservedProjectSpendMYR observed $($ObservedAt.ToString('u')); cap RM30."

# Create the all-service budget before enabling the hosted workload APIs.
Invoke-Gcloud @('services','enable','billingbudgets.googleapis.com','--project', $Project,'--quiet')
$ExistingBudgets = (& gcloud billing budgets list --billing-account=$BillingAccount --format=json --quiet | ConvertFrom-Json)
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect existing budgets' }
$MatchingBudgets = @($ExistingBudgets | Where-Object { $_.displayName -eq $BudgetName })
if ($MatchingBudgets.Count -gt 1) { throw 'Duplicate CP2 budgets; inspect before continuing' }
if ($MatchingBudgets.Count -eq 1) {
    $b = $MatchingBudgets[0]
    if ($b.amount.specifiedAmount.currencyCode -ne 'MYR' -or
        [decimal]$b.amount.specifiedAmount.units -ne 30 -or
        @($b.budgetFilter.projects).Count -ne 1 -or
        $b.budgetFilter.projects[0] -notin @("projects/$Project", "projects/$ProjectNumber")) {
        throw 'Existing CP2 budget does not match the RM30 project ceiling'
    }
    Write-Output 'Existing scoped RM30 budget verified.'
} else {
    Invoke-Gcloud @('billing','budgets','create','--billing-account', $BillingAccount,
        '--display-name', $BudgetName,'--budget-amount','30MYR','--calendar-period','month',
        '--filter-projects',"projects/$Project",'--threshold-rule','percent=0.50',
        '--threshold-rule','percent=0.80','--threshold-rule','percent=1.00',
        '--ownership-scope','all-users','--quiet')
}

Invoke-Gcloud @('services','enable','run.googleapis.com','cloudscheduler.googleapis.com',
    'secretmanager.googleapis.com','artifactregistry.googleapis.com',
    'iam.googleapis.com','iamcredentials.googleapis.com','sts.googleapis.com',
    'cloudresourcemanager.googleapis.com',
    '--project', $Project,'--quiet')

foreach ($id in @('cp2-reporting-job','cp2-reporting-scheduler','cp2-reporting-deployer')) {
    if (-not (Test-Gcloud @('iam','service-accounts','describe',"$id@$Project.iam.gserviceaccount.com",'--project',$Project))) {
        Invoke-Gcloud @('iam','service-accounts','create',$id,'--project',$Project,
            '--display-name',"CP2 $id",'--quiet')
    }
}

Invoke-Gcloud @('projects','add-iam-policy-binding',$Project,
    '--member',"serviceAccount:$JobIdentity",'--role','roles/bigquery.user','--quiet')
$Python = Join-Path (Resolve-Path (Join-Path $PSScriptRoot '..')).Path '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw 'Project Python environment is missing; bootstrap dataset grants require .venv'
}
& $Python (Join-Path $PSScriptRoot 'grant_bigquery_dataset_access.py') --apply
if ($LASTEXITCODE -ne 0) { throw 'BigQuery dataset ACL update failed' }

foreach ($name in $Secrets) {
    if (-not (Test-Gcloud @('secrets','describe',$name,'--project',$Project))) {
        Invoke-Gcloud @('secrets','create',$name,'--project',$Project,
            '--replication-policy','user-managed','--locations',$Region,'--quiet')
    }
    Invoke-Gcloud @('secrets','add-iam-policy-binding',$name,'--project',$Project,
        '--member',"serviceAccount:$JobIdentity",'--role','roles/secretmanager.secretAccessor','--quiet')
}

if (-not (Test-Gcloud @('artifacts','repositories','describe','cp2-reporting',
    '--location',$Region,'--project',$Project))) {
    Invoke-Gcloud @('artifacts','repositories','create','cp2-reporting',
        '--repository-format','docker','--location',$Region,'--project',$Project,
        '--description','CP2 reporting release images','--quiet')
}
Invoke-Gcloud @('artifacts','repositories','add-iam-policy-binding','cp2-reporting',
    '--location',$Region,'--project',$Project,'--member',"serviceAccount:$DeployerIdentity",
    '--role','roles/artifactregistry.writer','--quiet')
Invoke-Gcloud @('projects','add-iam-policy-binding',$Project,
    '--member',"serviceAccount:$DeployerIdentity",'--role','roles/run.developer','--quiet')
Invoke-Gcloud @('iam','service-accounts','add-iam-policy-binding',$JobIdentity,
    '--project',$Project,'--member',"serviceAccount:$DeployerIdentity",
    '--role','roles/iam.serviceAccountUser','--quiet')

if (-not (Test-Gcloud @('iam','workload-identity-pools','describe','cp2-github',
    '--location','global','--project',$Project))) {
    Invoke-Gcloud @('iam','workload-identity-pools','create','cp2-github',
        '--location','global','--project',$Project,
        '--display-name','CP2 GitHub deployments','--quiet')
}
if (-not (Test-Gcloud @('iam','workload-identity-pools','providers','describe','cp2-main',
    '--workload-identity-pool','cp2-github','--location','global','--project',$Project))) {
    $condition = "assertion.repository_id=='$RepoId' && assertion.repository_owner_id=='$OwnerId' && assertion.ref=='refs/heads/main' && assertion.event_name=='workflow_dispatch'"
    Invoke-Gcloud @('iam','workload-identity-pools','providers','create-oidc','cp2-main',
        '--workload-identity-pool','cp2-github','--location','global','--project',$Project,
        '--issuer-uri','https://token.actions.githubusercontent.com/',
        '--attribute-mapping','google.subject=assertion.sub,attribute.repository_id=assertion.repository_id,attribute.owner_id=assertion.repository_owner_id',
        '--attribute-condition',$condition,'--quiet')
}
$principal = "principalSet://iam.googleapis.com/projects/$ProjectNumber/locations/global/workloadIdentityPools/cp2-github/attribute.repository_id/$RepoId"
Invoke-Gcloud @('iam','service-accounts','add-iam-policy-binding',$DeployerIdentity,
    '--project',$Project,'--member',$principal,'--role','roles/iam.workloadIdentityUser','--quiet')

Write-Output 'Bootstrap complete. Seed the three private secrets, then run the manual GitHub deployment. The scheduler is provisioned separately after a successful manual execution.'
