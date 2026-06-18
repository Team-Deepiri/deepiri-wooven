param(
    [Parameter(Mandatory = $true)]
    [string]$Python
)

$ErrorActionPreference = "Stop"
$TaskName = "DeepiriGitHandshake"
$Action = New-ScheduledTaskAction -Execute $Python -Argument "-m deepiri_git_handshake.daemon --foreground"
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal | Out-Null
Start-ScheduledTask -TaskName $TaskName
Write-Output "Registered and started scheduled task: $TaskName"
