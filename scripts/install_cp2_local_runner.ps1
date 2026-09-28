param([ValidateSet('Status','Install','InstallFinal','Remove')][string]$Mode='Status')

$ErrorActionPreference='Stop'
$taskName='Nomobug CP2 Prospective Local'
$finalTaskName='Nomobug CP2 Final Evaluation'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python=Join-Path $root '.venv\Scripts\python.exe'
$runner=Join-Path $root 'scripts\cp2_pipeline_tick.py'

if ($Mode -eq 'Status') {
    foreach ($name in @($taskName,$finalTaskName)) {
        $task=Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
        if ($null -eq $task) {
            [pscustomobject]@{ TaskName=$name; State='Not installed' }
            continue
        }
        $info=Get-ScheduledTaskInfo -TaskName $name
        [pscustomobject]@{ TaskName=$name; State=$task.State;
            LastRunTime=$info.LastRunTime; LastTaskResult=$info.LastTaskResult;
            NextRunTime=$info.NextRunTime }
    }
    return
}
if ($Mode -eq 'Remove') {
    foreach ($name in @($taskName,$finalTaskName)) {
        if ($null -ne (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue)) {
            Unregister-ScheduledTask -TaskName $name -Confirm:$false
        }
    }
    Write-Output 'removed'
    return
}
if (-not (Test-Path -LiteralPath $python -PathType Leaf) -or
    -not (Test-Path -LiteralPath $runner -PathType Leaf)) {
    throw 'Project Python or prospective runner missing.'
}
if ($Mode -eq 'InstallFinal') {
    if ($null -ne (Get-ScheduledTask -TaskName $finalTaskName -ErrorAction SilentlyContinue)) {
        throw 'Final evaluation task already exists. Inspect it before replacing.'
    }
    $final=Join-Path $root 'scripts\cp2_pipeline.py'
    $action=New-ScheduledTaskAction -Execute $python -Argument ('"'+$final+'" final-evaluation') -WorkingDirectory $root
    $trigger=New-ScheduledTaskTrigger -Once -At ([datetime]::new(2026,11,27,9,0,0))
    $settings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 20) `
        -StartWhenAvailable
    $principal=New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) `
        -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $finalTaskName -Action $action -Trigger $trigger -Settings $settings `
        -Principal $principal -Description 'One-time complete-source CP2 future cohort evaluation; refuses missing logs.' | Out-Null
    Write-Output 'installed: one-time complete-source future evaluation on 27 November at 09:00 MYT.'
    return
}
if ($null -ne (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue)) {
    throw 'Task already exists. Inspect it before replacing.'
}
$action=New-ScheduledTaskAction -Execute $python -Argument ('"'+$runner+'"') -WorkingDirectory $root
$trigger=New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 2) -RepetitionDuration (New-TimeSpan -Days 31)
$settings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
    -StartWhenAvailable
$principal=New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) `
    -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings `
    -Principal $principal -Description 'CP2 Calendar-only trigger; full scoring on just-ended services.' | Out-Null
Write-Output 'installed: local interactive 2-minute trigger through 27 October cohort; computer must be awake.'
