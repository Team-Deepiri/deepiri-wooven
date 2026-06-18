$ErrorActionPreference = "Stop"
$TaskName = "DeepiriGitHandshake"
Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
Write-Output "Removed scheduled task: $TaskName"
