﻿#Requires -RunAsAdministrator
#Requires -Version 5.1
<#
.SYNOPSIS
    Install PMWB services for Windows auto-start (no login needed) + crash-restart.
      - MySQL-PMWB  : NATIVE Windows service (mysqld --install) - most reliable for mysqld
      - PMWB-Backend / PMWB-Frontend / PMWB-Mail : NSSM services
    Run as Administrator (right-click the desktop .bat -> Run as administrator).
#>

$ErrorActionPreference = "Stop"

try {
    if (-not (Test-Path "C:\pmwb-logs")) { New-Item -ItemType Directory -Path "C:\pmwb-logs" -Force | Out-Null }
    "$([DateTime]::Now.ToString('yyyy-MM-dd HH:mm:ss')) install-windows-services.ps1 started" | Out-File -FilePath "C:\pmwb-logs\install-script-started.marker" -Encoding UTF8 -Force
} catch {}

# ========================== Config ==========================
$NssmDir  = "C:\nssm"
$NssmExe  = Join-Path $NssmDir "nssm.exe"
$LogDir   = "C:\pmwb-logs"
$MySqlBase = "C:\mysql\mysql-8.0.46-winx64"
$MysqlServiceName = "MySQL-PMWB"
$MysqldExe = "$MySqlBase\bin\mysqld.exe"
$PmwbBase  = "D:\项目\个人工作台系统"
$MailBase  = "D:\项目\统一邮件中心\server"
$NodePath  = "C:\Users\chend\.workbuddy\binaries\node\versions\22.22.2\node.exe"

# NSSM-managed services. MySQL is installed as a NATIVE service (see below).
$Services = @(
    @{
        Name        = "PMWB-Backend"
        DisplayName = "PMWB FastAPI Backend"
        Description = "PMWB FastAPI backend on 0.0.0.0:8000"
        Program     = "$PmwbBase\backend\venv\Scripts\python.exe"
        Arguments   = "-m uvicorn main:app --host 0.0.0.0 --port 8000"
        WorkDir     = "$PmwbBase\backend"
        DependOn    = @("MySQL-PMWB")
    },
    @{
        Name        = "PMWB-Frontend"
        DisplayName = "PMWB Vite Frontend"
        Description = "PMWB Vite frontend on 127.0.0.1:5173"
        Program     = $NodePath
        Arguments   = "node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5173"
        WorkDir     = "$PmwbBase\frontend"
        DependOn    = @("PMWB-Backend")
    },
    @{
        Name        = "PMWB-Mail"
        DisplayName = "PMWB Mail Center"
        Description = "PMWB mail center on 127.0.0.1:3210"
        # IMPORTANT: tsx.cmd (NOT tsx) - tsx is a bash script that node.exe cannot run on Windows.
        Program     = $NodePath
        Arguments   = "node_modules/.bin/tsx.cmd src/index.ts"
        WorkDir     = $MailBase
        DependOn    = @()
    }
)

$NssmDownloadUrl = "https://nssm.cc/release/nssm-2.24.zip"

# ========================== Logging helpers ==========================
function Write-Log {
    param([string]$msg, [string]$level = "INFO")
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] [$level] $msg"
    Write-Host $line
    Add-Content -Path (Join-Path $LogDir "install-services.log") -Value $line -Encoding UTF8 -ErrorAction SilentlyContinue
}

function Ensure-Dir {
    param([string]$dir)
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
}

function Test-Port {
    param([int]$port)
    try {
        $conn = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
        return ($conn -ne $null)
    } catch { return $false }
}

function Wait-ForPort {
    param([int]$port, [int]$timeoutSec = 60)
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalSeconds -lt $timeoutSec) {
        if (Test-Port $port) { return $true }
        Start-Sleep -Seconds 1
    }
    return $false
}

# ========================== Pre-checks ==========================
Ensure-Dir $LogDir
Write-Log "===== PMWB Windows service install started ====="

$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Log "ERROR: Run this script as Administrator." "ERROR"
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Log "Admin check: OK"

$pathsOk = $true
foreach ($p in @($MySqlBase, $PmwbBase, $MailBase, $NodePath)) {
    if (-not (Test-Path $p)) {
        Write-Log "Path not found: $p" "ERROR"
        $pathsOk = $false
    }
}
if (-not $pathsOk) {
    Write-Log "ERROR: Please check the paths in the script config." "ERROR"
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Log "Path check: OK"

# ========================== Install NSSM ==========================
if (-not (Test-Path $NssmExe)) {
    Write-Log "NSSM not found, downloading..."
    Ensure-Dir $NssmDir
    $zip = Join-Path $NssmDir "nssm.zip"
    try {
        Invoke-WebRequest -Uri $NssmDownloadUrl -OutFile $zip -UseBasicParsing -TimeoutSec 120
        Write-Log "Downloaded: $zip"
    } catch {
        Write-Log "Failed to download NSSM: $($_.Exception.Message)" "ERROR"
        Write-Log "Please download $NssmDownloadUrl and extract nssm.exe to $NssmDir" "ERROR"
        Read-Host "Press Enter to exit"
        exit 1
    }
    $tmp = Join-Path $NssmDir "_tmp"
    Expand-Archive -Path $zip -DestinationPath $tmp -Force
    $arch = if ([Environment]::Is64BitOperatingSystem) { "win64" } else { "win32" }
    $src = Join-Path $tmp "nssm-2.24\$arch\nssm.exe"
    Copy-Item -Path $src -Destination $NssmExe -Force
    Remove-Item -Path $tmp -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -Path $zip -Force -ErrorAction SilentlyContinue
    Write-Log "NSSM installed at: $NssmExe"
} else {
    Write-Log "NSSM already exists: $NssmExe"
}

# ========================== Stop old processes ==========================
Write-Log "Stopping old processes (so ports are free)..."
$procsToKill = @("mysqld", "uvicorn", "node", "vite", "tsx")
foreach ($proc in $procsToKill) {
    Get-Process -Name $proc -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 3

# ========================== MySQL : NATIVE Windows service ==========================
Write-Log "Setting up native MySQL service: $MysqlServiceName"
# Remove any prior MySQL-PMWB (NSSM-managed or native) so we start clean.
$existingMy = Get-Service -Name $MysqlServiceName -ErrorAction SilentlyContinue
if ($existingMy) {
    try { Stop-Service -Name $MysqlServiceName -Force -ErrorAction Stop } catch { Write-Log "  stop failed: $($_.Exception.Message)" "WARN" }
    Start-Sleep -Seconds 2
    # If it was NSSM-managed, remove via nssm; otherwise via sc.
    try {
        $img = (Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Services\$MysqlServiceName" -Name ImagePath -ErrorAction Stop).ImagePath
    } catch { $img = "" }
    if ($img -like "*nssm*") {
        & $NssmExe remove $MysqlServiceName confirm 2>$null
    }
    # Always attempt sc delete to guarantee a clean slate before mysqld --install.
    & sc.exe delete $MysqlServiceName 2>$null
    Start-Sleep -Seconds 2
}

Write-Log "  mysqld --install $MysqlServiceName ..."
& $MysqldExe --install $MysqlServiceName --defaults-file="$MySqlBase\my.ini" | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Log "  mysqld --install returned code $LASTEXITCODE (may already exist; continuing)" "WARN"
}
# Auto-start + restart on failure.
& sc.exe config $MysqlServiceName start= auto 2>$null
& sc.exe failure $MysqlServiceName reset= 0 actions= restart/5000/restart/10000/restart/60000 2>$null
Write-Log "  native MySQL service configured (auto-start, restart-on-failure)"

# ========================== Install / reinstall NSSM services ==========================
foreach ($svc in $Services) {
    $name = $svc.Name
    Write-Log "Processing service: $name"

    $existing = Get-Service -Name $name -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Log "  Service exists, stopping and removing..."
        try { Stop-Service -Name $name -Force -ErrorAction Stop } catch { Write-Log "  Stop failed: $($_.Exception.Message)" "WARN" }
        Start-Sleep -Seconds 2
        & $NssmExe remove $name confirm | Out-Null
        Start-Sleep -Seconds 1
    }

    Write-Log "  Installing service..."
    & $NssmExe install $name $svc.Program | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "nssm install $name failed" }

    & $NssmExe set $name DisplayName $svc.DisplayName | Out-Null
    & $NssmExe set $name Description $svc.Description | Out-Null
    & $NssmExe set $name Application $svc.Program | Out-Null
    & $NssmExe set $name AppParameters $svc.Arguments | Out-Null
    & $NssmExe set $name AppDirectory $svc.WorkDir | Out-Null
    & $NssmExe set $name Start SERVICE_AUTO_START | Out-Null
    & $NssmExe set $name AppStdout (Join-Path $LogDir "$name-stdout.log") | Out-Null
    & $NssmExe set $name AppStderr (Join-Path $LogDir "$name-stderr.log") | Out-Null
    & $NssmExe set $name AppStdoutCreationDisposition 2 | Out-Null
    & $NssmExe set $name AppStderrCreationDisposition 2 | Out-Null
    & $NssmExe set $name AppRotateFiles 1 | Out-Null
    & $NssmExe set $name AppRotateBytes 10485760 | Out-Null
    & $NssmExe set $name AppExit Default Restart | Out-Null
    & $NssmExe set $name AppRestartDelay 5000 | Out-Null

    if ($svc.DependOn.Count -gt 0) {
        $dep = $svc.DependOn -join "/"
        & $NssmExe set $name DependOnService $dep | Out-Null
    }

    Write-Log "  Service $name installed"
}

# ========================== Start MySQL first, wait for 3306 ==========================
Write-Log "Starting MySQL native service (with retry)..."
$mysqlOk = $false
for ($i = 1; $i -le 3; $i++) {
    & sc.exe start $MysqlServiceName 2>$null
    $mysqlOk = Wait-ForPort -port 3306 -timeoutSec 30
    if ($mysqlOk) { Write-Log "  MySQL 3306 ready (attempt $i)" "OK"; break }
    Write-Log "  MySQL not ready on attempt $i, retrying..." "WARN"
    Start-Sleep -Seconds 3
}
if (-not $mysqlOk) { Write-Log "  WARNING: MySQL did not come up; backends may fail until it does." "ERROR" }

# ========================== Start NSSM services ==========================
Write-Log "Starting NSSM services..."
foreach ($svc in $Services) {
    $name = $svc.Name
    Start-Service -Name $name -ErrorAction SilentlyContinue
    Write-Log "  Started: $name"
}
Write-Log "Waiting for services to be ready..."
Start-Sleep -Seconds 3

# ========================== Verify ==========================
$ports = @{3306 = "MySQL-PMWB (native)"; 8000 = "PMWB-Backend"; 5173 = "PMWB-Frontend"; 3210 = "PMWB-Mail"}
$allOk = $true
foreach ($port in $ports.Keys) {
    $ready = Wait-ForPort -port $port -timeoutSec 60
    if ($ready) {
        Write-Log "  :$port ready [$($ports[$port])]" "OK"
    } else {
        Write-Log "  :$port not ready [$($ports[$port])]" "ERROR"
        $allOk = $false
    }
}

Write-Log ""
Write-Log "Service summary:"
try { & sc.exe query $MysqlServiceName 2>$null | Select-String "STATE" | ForEach-Object { Write-Log "  $MysqlServiceName : $_" } } catch {}
Get-Service -Name @($Services.Name) | ForEach-Object {
    Write-Log "  $($_.Name) : $($_.Status)"
}

if ($allOk) {
    Write-Log "===== Install successful, all services ready =====" "OK"
    Write-Log "Open http://127.0.0.1:5173" "OK"
} else {
    Write-Log "===== Some services not ready, check logs =====" "ERROR"
    Write-Log "  - MySQL error log: $MySqlBase\data\*.err" "ERROR"
    Write-Log "  - Service logs: $LogDir" "ERROR"
}

Read-Host "Press Enter to exit"
