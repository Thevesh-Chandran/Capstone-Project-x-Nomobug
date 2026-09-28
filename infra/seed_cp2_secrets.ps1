<#
.SYNOPSIS
Upload the approved read-only Google credential and source inventory privately.
.DESCRIPTION
Creates one Secret Manager version per file. The source files stay under
ignored local paths. A repeated upload requires -Rotate to avoid unnecessary
versions and charges. Values are never printed.
#>
param(
    [Parameter(Mandatory=$true)][string]$TokenPath,
    [Parameter(Mandatory=$true)][string]$SourceIdsPath,
    [Parameter(Mandatory=$true)][string]$MetadataPath,
    [switch]$Apply,
    [switch]$Rotate
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Project = 'profound-keel-500007-s4'
$Sources = @(
    @{ Name = 'cp2-google-readonly-token'; Path = $TokenPath },
    @{ Name = 'cp2-google-source-ids'; Path = $SourceIdsPath },
    @{ Name = 'cp2-google-source-metadata'; Path = $MetadataPath }
)
foreach ($item in $Sources) {
    $item.Path = (Resolve-Path -LiteralPath $item.Path).Path
    if (-not (Test-Path -LiteralPath $item.Path -PathType Leaf)) {
        throw "Required private file missing: $($item.Name)"
    }
    $parsed = Get-Content -LiteralPath $item.Path -Raw -Encoding UTF8 | ConvertFrom-Json
    switch ($item.Name) {
        'cp2-google-readonly-token' {
            $allowed = @('https://www.googleapis.com/auth/spreadsheets.readonly',
                         'https://www.googleapis.com/auth/calendar.readonly')
            $actual = @($parsed.scopes)
            if ($actual.Count -ne 2 -or @($actual | Where-Object { $_ -notin $allowed }).Count -gt 0 -or
                -not $parsed.refresh_token -or -not $parsed.client_id -or -not $parsed.client_secret) {
                throw 'OAuth file lacks the two approved read-only scopes or refresh fields'
            }
        }
        'cp2-google-source-ids' {
            if (@($parsed.spreadsheet_ids).Count -lt 1) { throw 'Approved spreadsheet ID list is empty' }
        }
        'cp2-google-source-metadata' {
            if (@($parsed.spreadsheets).Count -lt 2 -or @($parsed.calendars).Count -lt 6) {
                throw 'Source metadata inventory is incomplete'
            }
        }
    }
}

if (-not $Apply) {
    Write-Output 'Three private JSON files validated. Dry-run only; no secret values uploaded.'
    return
}
foreach ($item in $Sources) {
    & gcloud secrets describe $item.Name --project $Project --quiet --format='value(name)' 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Secret container absent: $($item.Name); run bootstrap first" }
    $versions = @(& gcloud secrets versions list $item.Name --project $Project --quiet --format='value(name)' 2>$null)
    if ($LASTEXITCODE -ne 0) { throw "Cannot inspect versions: $($item.Name)" }
    if (@($versions | Where-Object { $_ }).Count -gt 0 -and -not $Rotate) {
        throw "Existing version for $($item.Name); use -Rotate only for an intentional rotation"
    }
}
foreach ($item in $Sources) {
    & gcloud secrets versions add $item.Name --project $Project --data-file $item.Path --quiet --format='value(name)'
    if ($LASTEXITCODE -ne 0) { throw "Version upload failed: $($item.Name)" }
    Write-Output "Uploaded one version for $($item.Name)."
}
