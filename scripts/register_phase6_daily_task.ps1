$ErrorActionPreference = "Stop"
$taskName = "InvestOSVN Phase6 Daily Refresh"
$repo = "C:\Users\DUC\.openclaw\workspace\invest-os-vn"
$script = Join-Path $repo "scripts\daily_refresh_phase6.ps1"

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`"" -WorkingDirectory $repo
$trigger = New-ScheduledTaskTrigger -Daily -At 18:10
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description "InvestOS VN real-only daily refresh: macro, market, news, audit, E2E, validation" -Force | Out-Null
Write-Output "PHASE6_TASK_REGISTERED: $taskName"
