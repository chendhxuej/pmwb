$ErrorActionPreference = 'Continue'
# install-windows-services.ps1
# 以管理员身份运行。将 PMWB 四件套注册为开机自启（无需登录）。
# 设计要点：
#   - MySQL 用「任务计划程序」以 SYSTEM 身份 detached 启动 mysqld。
#     服务模式在本机必失败：原生 Windows 服务报 1053、NSSM 包 mysqld 都 PAUSED；
#     只有普通控制台进程（=平时手动/脚本能跑的命令）才能稳定起来。
#   - 后端/邮件/前端 用 NSSM 包装普通进程（已验证 AppParameters 正确即可正常起）。
#   - 后端经 backend-launch.ps1 等待 3306 就绪再起 uvicorn，消除开机启动竞态。
#   - 邮件用 cmd /c tsx.cmd（node 不能直接跑 .cmd）；前端用 node node_modules/vite/bin/vite.js。
#   - 启动前先杀相关进程释放句柄/数据目录锁，避免 1072 与残留。

$logDir = "C:\pmwb-logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
$logFile = Join-Path $logDir "install-services.log"

function Write-Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] $msg"
    Write-Host $line
    try { Add-Content -Path $logFile -Value $line -Encoding UTF8 } catch {}
}

function Wait-ForPort($port, $timeout = 90) {
    $t = 0
    while ($t -lt $timeout) {
        try {
            $c = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
            if ($c) { return $true }
        } catch {}
        Start-Sleep -Seconds 1; $t++
    }
    return $false
}

function Stop-PortProcess($port) {
    try {
        $pids = (Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue).OwningProcess | Sort-Object -Unique
        foreach ($pid in $pids) {
            if ($pid -and $pid -ne 0) {
                Write-Log "  killing stale pid $pid on :$port"
                taskkill.exe /F /PID $pid /T 2>$null | Out-Null
            }
        }
    } catch {}
}

function Kill-ByName($img) {
    try { taskkill.exe /F /IM $img 2>$null | Out-Null } catch {}
}

Write-Log "===== PMWB Windows service install started ====="

# 0. admin check
$id = [System.Security.Principal.WindowsIdentity]::GetCurrent()
$princ = New-Object System.Security.Principal.WindowsPrincipal($id)
if (-not $princ.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Log "[ERROR] 需要管理员权限。请右键 pmwb-install-services.bat -> 以管理员身份运行"
    Write-Log "===== Install FAILED (no admin) ====="
    exit 1
}
Write-Log "Admin check: OK"

# paths
$NssmExe    = "C:\nssm\nssm.exe"
$MysqlBin   = "C:\mysql\mysql-8.0.46-winx64\bin\mysqld.exe"
$MysqlIni   = "C:\mysql\mysql-8.0.46-winx64\my.ini"
$NodePath   = "C:\Users\chend\.workbuddy\binaries\node\versions\22.22.2\node.exe"
$BackendDir  = "D:\项目\个人工作台系统\backend"
$FrontendDir = "D:\项目\个人工作台系统\frontend"
$MailDir    = "D:\项目\统一邮件中心\server"
$BackendPy  = "$BackendDir\venv\Scripts\python.exe"
$MailTsx    = "$MailDir\node_modules\.bin\tsx.cmd"
$BackendLaunch = "C:\pmwb-scripts\backend-launch.ps1"

$MysqlTask  = "PMWB-MySQL"
$svcBackend  = "PMWB-Backend"
$svcFrontend = "PMWB-Frontend"
$svcMail     = "PMWB-Mail"

foreach ($p in @($NssmExe, $MysqlBin, $MysqlIni, $NodePath, $BackendPy, $FrontendDir, $MailDir, $MailTsx, $BackendLaunch)) {
    if (-not (Test-Path $p)) { Write-Log "[ERROR] Path missing: $p"; Write-Log "===== Install FAILED (path) ====="; exit 1 }
}
Write-Log "Path check: OK"

# 1. 杀掉所有相关进程，释放句柄（避免 1072）与 MySQL 数据目录锁
Write-Log "Killing related processes to release handles ..."
Kill-ByName "nssm.exe"
Kill-ByName "mysqld.exe"
Kill-ByName "node.exe"
foreach ($port in @(3306, 8000, 5173, 3210)) { Stop-PortProcess $port }
Start-Sleep -Seconds 2

# 2. 删除所有相关服务/任务（旧的 + 本次已创建的），保证每次都是干净重装
Write-Log "Removing old/new services ..."
$AllSvcs = @("MySQLPMWB", $svcBackend, $svcFrontend, $svcMail, "MySQL-PMWB")
foreach ($s in $AllSvcs) {
    $key = "HKLM:\SYSTEM\CurrentControlSet\Services\$s"
    $img = $null
    try { $img = (Get-ItemProperty $key -ErrorAction SilentlyContinue).ImagePath } catch {}
    if ($img -like "*nssm*") {
        & $NssmExe stop $s 2>$null
        & $NssmExe remove $s confirm 2>$null
    } else {
        & sc.exe stop $s 2>$null
    }
    & sc.exe delete $s 2>$null
    Start-Sleep -Seconds 1
    $still = $null
    try { $still = Get-Service -Name $s -ErrorAction SilentlyContinue } catch {}
    if ($still) {
        Write-Log "  [WARN] $s 仍处于待删除状态"
        Write-Log "[ERROR] 检测到服务处于'待删除'状态，请先【重启电脑】，再重新运行本安装脚本。"
        Write-Log "===== Install FAILED (reboot required) ====="
        exit 1
    } else {
        Write-Log "  removed: $s"
    }
}
# 删除旧的 MySQL 计划任务（若有）
try {
    $mt = Get-ScheduledTask -TaskName $MysqlTask -ErrorAction SilentlyContinue
    if ($mt) { Unregister-ScheduledTask -TaskName $MysqlTask -Confirm:$false; Write-Log "  removed task: $MysqlTask" }
} catch {}

# 3. 安装 3 个 NSSM 服务（应用进程）
function Install-Nssm($name, $exe, $appArgs, $appDir, $depend) {
    Write-Log "Processing service: $name"
    & $NssmExe install $name $exe 2>&1 | ForEach-Object { Write-Log "  nssm install: $_" }
    if ($appArgs) {
        & $NssmExe set $name AppParameters "$appArgs" 2>&1 | ForEach-Object { Write-Log "  nssm set args: $_" }
    }
    if ($appDir) { & $NssmExe set $name AppDirectory "$appDir" 2>$null }
    & $NssmExe set $name AppStdout "$logDir\$name-stdout.log" 2>$null
    & $NssmExe set $name AppStderr "$logDir\$name-stderr.log" 2>$null
    & $NssmExe set $name AppExit Default Restart 2>$null
    & $NssmExe set $name Start SERVICE_AUTO_START 2>$null
    if ($depend) { & $NssmExe set $name DependOnService $depend 2>$null }
    & sc.exe failure $name reset= 0 actions= restart/1000/restart/1000/restart/1000 2>$null
    Write-Log "  Service $name installed"
}

# 后端：经 backend-launch.ps1 等待 3306 再起 uvicorn（靠脚本等待，无需服务级依赖）
Install-Nssm $svcBackend "powershell.exe" "-ExecutionPolicy Bypass -File `"$BackendLaunch`"" $null $null
# 邮件：cmd /c tsx.cmd
$mailArgs = "/c `"$MailTsx`" src/index.ts"
Install-Nssm $svcMail "cmd.exe" $mailArgs $MailDir $null
# 前端：vite
Install-Nssm $svcFrontend $NodePath "node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5173" $FrontendDir $null

# 3b. 校验 AppParameters 已写入（防止 PowerShell $args 自动变量吞参的坑导致空参数服务）
Write-Log "Verifying AppParameters ..."
foreach ($s in @($svcBackend, $svcMail, $svcFrontend)) {
    $ap = (Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Services\$s\Parameters" -ErrorAction SilentlyContinue).AppParameters
    if ([string]::IsNullOrWhiteSpace($ap)) {
        Write-Log "[ERROR] $s AppParameters 为空，安装中止（参数未被 NSSM 接收）"
        Write-Log "===== Install FAILED (empty args) ====="
        exit 1
    } else {
        Write-Log "  $s AppParameters OK: $ap"
    }
}

# 3c. 安装 MySQL 计划任务（SYSTEM，开机自启，无需登录；崩溃自动重启 3 次/间隔 1 分钟）
Write-Log "Installing MySQL startup task ($MysqlTask) ..."
try {
    $mtAction = New-ScheduledTaskAction -Execute $MysqlBin -Argument "--defaults-file=$MysqlIni"
    $mtTrigger = New-ScheduledTaskTrigger -AtStartup
    $mtSettings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Days 3650)
    Register-ScheduledTask -TaskName $MysqlTask -Action $mtAction -Trigger $mtTrigger -User "SYSTEM" -RunLevel Highest -Settings $mtSettings -Force | Out-Null
    Write-Log "  MySQL task registered (SYSTEM, at startup)"
} catch {
    Write-Log "  [ERROR] register MySQL task failed: $_"
    Write-Log "===== Install FAILED (mysql task) ====="
    exit 1
}

# 4. 按顺序启动：先 MySQL 任务，等 3306，再起 3 个 NSSM 服务
Write-Log "Starting MySQL task ..."
try { Start-ScheduledTask -TaskName $MysqlTask -ErrorAction Stop } catch { Write-Log "  [WARN] start MySQL task: $_" }
if (-not (Wait-ForPort 3306 90)) {
    Write-Log "[ERROR] MySQL :3306 not ready"
} else {
    Write-Log "[OK] MySQL :3306 ready"
}

& $NssmExe start $svcBackend 2>&1 | ForEach-Object { Write-Log "  nssm start backend: $_" }
& $NssmExe start $svcMail 2>&1 | ForEach-Object { Write-Log "  nssm start mail: $_" }
& $NssmExe start $svcFrontend 2>&1 | ForEach-Object { Write-Log "  nssm start frontend: $_" }

# 5. 校验
Start-Sleep -Seconds 3
$b = Wait-ForPort 8000 40
$m = Wait-ForPort 3210 40
$f = Wait-ForPort 5173 40

Write-Log ""
Write-Log "Service summary:"
Write-Log "  $MysqlTask : $((Get-ScheduledTask -TaskName $MysqlTask -ErrorAction SilentlyContinue).State)  (:3306 $(Wait-ForPort 3306 1))"
Write-Log "  $svcBackend : $((Get-Service $svcBackend -ErrorAction SilentlyContinue).Status)  (:8000 $b)"
Write-Log "  $svcMail : $((Get-Service $svcMail -ErrorAction SilentlyContinue).Status)  (:3210 $m)"
Write-Log "  $svcFrontend : $((Get-Service $svcFrontend -ErrorAction SilentlyContinue).Status)  (:5173 $f)"

if ((Wait-ForPort 3306 1) -and $b -and $m -and $f) {
    Write-Log "===== Install successful, all services ready ====="
    Write-Log "Open http://127.0.0.1:5173"
} else {
    Write-Log "===== Some services not ready, check $logDir ====="
}
