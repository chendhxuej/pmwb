# backend-wrapper.ps1
# NSSM 服务入口：先等 MySQL(3306) 就绪，再拉起 uvicorn，并阻塞以保持服务存活。
$ErrorActionPreference = 'Stop'

$mysqlPort = 3306
$maxWait   = 180
$ready     = $false

for ($i = 0; $i -lt $maxWait; $i++) {
    try {
        $conn = Get-NetTCPConnection -LocalPort $mysqlPort -ErrorAction SilentlyContinue
        if ($conn) { $ready = $true; break }
    } catch {}
    Start-Sleep -Seconds 1
}

if (-not $ready) {
    Write-Host "[backend-wrapper] MySQL :$mysqlPort not ready after ${maxWait}s, exiting (NSSM will retry)"
    exit 1
}

Write-Host "[backend-wrapper] MySQL ready, launching uvicorn on :8000 ..."
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName        = "D:\项目\个人工作台系统\backend\venv\Scripts\python.exe"
$psi.Arguments       = "-m uvicorn main:app --host 0.0.0.0 --port 8000"
$psi.WorkingDirectory = "D:\项目\个人工作台系统\backend"
$psi.UseShellExecute = $false
$psi.CreateNoWindow  = $true
$p = [System.Diagnostics.Process]::Start($psi)
$p.WaitForExit()
exit $p.ExitCode
