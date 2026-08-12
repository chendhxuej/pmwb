$ErrorActionPreference = 'Continue'
# backend-launch.ps1
# 等待 MySQL(3306) 就绪后再启动 uvicorn，消除开机启动时的竞态。
# 由 NSSM(PMWB-Backend) 以 powershell -File 方式调用。

$mysqlPort  = 3306
$BackendPy  = "D:\项目\个人工作台系统\backend\venv\Scripts\python.exe"
$BackendDir = "D:\项目\个人工作台系统\backend"

$t = 0
while ($t -lt 120) {
    try {
        $c = Get-NetTCPConnection -LocalPort $mysqlPort -ErrorAction SilentlyContinue
        if ($c) { break }
    } catch {}
    Start-Sleep -Seconds 1
    $t++
}
if ($t -ge 120) {
    Write-Host "[backend-launch] WARNING: MySQL :$mysqlPort not ready after 120s, starting uvicorn anyway"
} else {
    Write-Host "[backend-launch] MySQL :$mysqlPort ready after ${t}s"
}

Set-Location $BackendDir
& $BackendPy -m uvicorn main:app --host 0.0.0.0 --port 8000
