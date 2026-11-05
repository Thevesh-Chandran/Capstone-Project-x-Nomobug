# Local preview uses approved cloud snapshots; credentials stay in local Google auth.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $projectRoot
$env:CP2_PORTAL_GCS_URI = 'gs://cp2-portal-profound-keel-500007-s4/current'
& "$projectRoot/.venv/Scripts/python.exe" -X utf8 -m webapp.server --port 8094 --data outputs/website_design/20261102_verified/runtime
