#Requires -RunAsAdministrator
#Requires -Version 5.1
<#
.SYNOPSIS
    Uninstall PMWB Windows services.
#>

$ErrorActionPreference = "Stop"

$NssmDir = "C:\nssm"
$NssmExe = Join-Path $NssmDir "nssm.exe"
$Services = @("PMWB-Mail", "PMWB-Frontend", "PMWB-Backend", "MySQL-PMWB")

$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "ERROR: Run this script as Administrator." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

foreach ($name in $Services) {
    $svc = Get-Service -Name $name -ErrorAction SilentlyContinue
    if (-not $svc) {
        Write-Host "Service not found, skip: $name" -ForegroundColor Yellow
        continue
    }

    Write-Host "Stopping service: $name"
    try { Stop-Service -Name $name -Force -ErrorAction Stop } catch { Write-Host "  Stop failed: $($_.Exception.Message)" -ForegroundColor Yellow }

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

Write-Host ""
Write-Host "Uninstall complete. Use desktop pmwb-start.bat to start services manually." -ForegroundColor Green
Read-Host "Press Enter to exit"
