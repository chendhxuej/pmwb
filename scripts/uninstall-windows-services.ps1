$ErrorActionPreference = 'Continue'
# uninstall-windows-services.ps1
# 以管理员身份运行。卸载 PMWB 四件套（3 个 NSSM 服务 + MySQL 计划任务）。
$logFile = "C:\pmwb-logs\uninstall-services.log"
$logDir  = "C:\pmwb-logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }

function Write-Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] $msg"
    Write-Host $line
    Add-Content -Path $logFile -Value $line -Encoding UTF8
}

$NssmExe = "C:\nssm\nssm.exe"
$MysqlTask = "PMWB-MySQL"
$svcs = @("MySQL-PMWB", "MySQLPMWB", "PMWB-Backend", "PMWB-Frontend", "PMWB-Mail")

Write-Log "===== PMWB Windows service uninstall started ====="

# 先删 MySQL 计划任务（SYSTEM 身份，独立于 NSSM）
try {
    $mt = Get-ScheduledTask -TaskName $MysqlTask -ErrorAction SilentlyContinue
    if ($mt) {
        try { Stop-ScheduledTask -TaskName $MysqlTask -ErrorAction SilentlyContinue } catch {}
        Unregister-ScheduledTask -TaskName $MysqlTask -Confirm:$false
        Write-Log "  removed task: $MysqlTask"
    } else {
        Write-Log "  task not present: $MysqlTask (skip)"
    }
} catch { Write-Log "  [WARN] remove task $MysqlTask : $_" }

$needsReboot = $false
foreach ($s in $svcs) {
    $key = "HKLM:\SYSTEM\CurrentControlSet\Services\$s"
    $img = $null
    try { $img = (Get-ItemProperty $key -ErrorAction SilentlyContinue).ImagePath } catch {}
    if ($img) {
        Write-Log "Removing $s ..."
        if ($img -like "*nssm*") {
            & $NssmExe stop $s 2>$null
            & $NssmExe remove $s confirm 2>$null
        } else {
            & sc.exe stop $s 2>$null
            Start-Sleep -Seconds 1
        }
        & sc.exe delete $s 2>$null
        Start-Sleep -Seconds 1
        $still = $null
        try { $still = Get-Service -Name $s -ErrorAction SilentlyContinue } catch {}
        if ($still) {
            Write-Log "  [WARN] $s 处于待删除状态，需重启电脑后才能清除"
            $needsReboot = $true
        } else {
            Write-Log "  removed: $s"
        }
    } else {
        Write-Log "  not present: $s (skip)"
    }
}
if ($needsReboot) {
    Write-Log "[WARN] 有服务处于待删除状态，请重启电脑后再次运行卸载脚本以彻底清理。"
    Write-Log "===== Uninstall finished (reboot needed) ====="
} else {
    Write-Log "===== Uninstall finished ====="
}
