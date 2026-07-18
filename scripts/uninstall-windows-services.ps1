#Requires -RunAsAdministrator
#Requires -Version 5.1
<#
.SYNOPSIS
    Uninstall PMWB Windows services.
      - MySQL-PMWB : native service (removed via sc delete)
      - PMWB-Backend / PMWB-Frontend / PMWB-Mail : NSSM services
    Run as Administrator.
#>

$ErrorActionPreference = "Stop"

$NssmDir = "C:\nssm"
$NssmExe = Join-Path $NssmDir "nssm.exe"
$MysqlServiceName = "MySQL-PMWB"
# NSSM-managed services
$NssmServices = @("PMWB-Mail", "PMWB-Frontend", "PMWB-Backend")

$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "ERROR: Run this script as Administrator." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# ---- Remove NSSM services ----
foreach ($name in $NssmServices) {
    $svc = Get-Service -Name $name -ErrorAction SilentlyContinue
    if (-not $svc) {
        Write-Host "Service not found, skip: $name" -ForegroundColor Yellow
        continue
    }
    Write-Host "Stopping service: $name"
    try { Stop-Service -Name $name -Force -ErrorAction Stop } catch { Write-Host "  Stop failed: $($_.Exception.Message)" -ForegroundColor Yellow }
    Start-Sleep -Seconds 1

    if (Test-Path $NssmExe) {
        Write-Host "Removing NSSM service: $name"
        & $NssmExe remove $name confirm | Out-Null
    } else {
        Write-Host "WARNING: NSSM not found, trying sc delete $name" -ForegroundColor Yellow
        & sc.exe delete $name | Out-Null
    }
    Start-Sleep -Seconds 1
    Write-Host "Uninstalled: $name" -ForegroundColor Green
}

# ---- Remove native MySQL service ----
$mySvc = Get-Service -Name $MysqlServiceName -ErrorAction SilentlyContinue
if ($mySvc) {
    Write-Host "Stopping MySQL service: $MysqlServiceName"
    try { Stop-Service -Name $MysqlServiceName -Force -ErrorAction Stop } catch { Write-Host "  Stop failed: $($_.Exception.Message)" -ForegroundColor Yellow }
    Start-Sleep -Seconds 2
    Write-Host "Deleting native MySQL service: $MysqlServiceName"
    & sc.exe delete $MysqlServiceName | Out-Null
    Start-Sleep -Seconds 1
    Write-Host "Uninstalled: $MysqlServiceName" -ForegroundColor Green
} else {
    Write-Host "MySQL service not found, skip: $MysqlServiceName" -ForegroundColor Yellow
}

# ---- Kill any leftover processes ----
Write-Host "Killing leftover processes..."
foreach ($proc in @("mysqld", "uvicorn", "node", "vite", "tsx")) {
    Get-Process -Name $proc -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "Uninstall complete." -ForegroundColor Green
Read-Host "Press Enter to exit"
