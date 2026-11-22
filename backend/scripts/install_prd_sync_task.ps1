# PRD 知识同步计划任务安装器 —— 老大本人 PowerShell 执行一次。
# 以当前登录用户(chend)身份运行 worker，GCM 内网 Git 凭据留在用户态，服务端零凭据。
# 后端 LocalSystem 只负责写请求/触发任务/读状态，绝不接触凭据。

$ErrorActionPreference = 'Stop'
$TaskName = 'PMWB-PRD-KnowledgeSync'
$Worker = 'D:\项目\个人工作台系统\backend\venv\Scripts\python.exe'
$WorkerScript = 'D:\项目\个人工作台系统\backend\scripts\prd_knowledge_sync_worker.py'
$User = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

if (-not (Test-Path $Worker)) { throw "Python not found: $Worker" }
if (-not (Test-Path $WorkerScript)) { throw "Worker not found: $WorkerScript" }

$action = New-ScheduledTaskAction -Execute $Worker -Argument "`"$WorkerScript`""
$principal = New-ScheduledTaskPrincipal -UserId $User -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 25) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$task = New-ScheduledTask -Action $action -Principal $principal -Settings $settings

Register-ScheduledTask -TaskName $TaskName -InputObject $task -Force | Out-Null
Write-Host "INSTALLED: $TaskName (user=$User)"
Write-Host "Verify: Get-ScheduledTask -TaskName $TaskName | Select TaskName,State"
Write-Host "Manual test: Start-ScheduledTask -TaskName $TaskName"
