@echo off
chcp 65001 >nul
echo 正在启动产品经理个人工作台...
echo.

REM ============ 统一入口：拉起 后端(8000) / 前端(5173) / 邮件中心(3210) ============
REM 端口感知：若已监听则先结束旧进程再拉起，确保用上最新代码（避免重复实例绑定失败）。

set BACKEND_DIR=D:\项目\个人工作台系统\backend
set FRONTEND_DIR=D:\项目\个人工作台系统\frontend
set MAIL_CENTER_DIR=D:\项目\统一邮件中心\server

REM ---------- MySQL(3306) 必须先于后端启动 ----------
REM 注意：本机 MySQL80 Windows 服务已损坏(net start 报 2186)，改用进程直拉(免管理员、已验证可用)。
set MYSQL_BIN=C:\mysql\mysql-8.0.46-winx64\bin\mysqld.exe
set MYSQL_INI=C:\mysql\mysql-8.0.46-winx64\my.ini
netstat -ano 2>nul | findstr /r ":3306 .*LISTEN" >nul
if errorlevel 1 (
  if exist "%MYSQL_BIN%" (
    echo 启动 MySQL(3306)...
    start "MySQL" /min "%MYSQL_BIN%" --defaults-file="%MYSQL_INI%"
    timeout /t 6 /nobreak >nul
  ) else (
    echo [警告] 未找到 mysqld.exe，请确认 MySQL 安装路径
  )
) else (
  echo MySQL(3306) 已在运行，跳过
)

REM ---------- 后端(8000) ----------
netstat -ano 2>nul | findstr /r ":8000 .*LISTEN" >nul
if not errorlevel 1 (
  echo 检测到旧的后端进程，先结束以加载最新代码...
  for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTEN"') do taskkill /PID %%p /F >nul 2>&1
  timeout /t 2 /nobreak >nul
)
start "PMWB Backend" "%BACKEND_DIR%\scripts\run_dev.bat"
timeout /t 3 /nobreak >nul

REM ---------- 前端(5173) ----------
netstat -ano 2>nul | findstr /r ":5173 .*LISTEN" >nul
if not errorlevel 1 (
  echo 检测到旧的前端进程，先结束以加载最新代码...
  for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5173" ^| findstr "LISTEN"') do taskkill /PID %%p /F >nul 2>&1
  timeout /t 2 /nobreak >nul
)
start "PMWB Frontend" "%FRONTEND_DIR%\scripts\run_dev.bat"
timeout /t 2 /nobreak >nul

REM ---------- 统一邮件中心(3210) 纳管：未监听则拉起，已运行则跳过 ----------
netstat -ano 2>nul | findstr /r ":3210 .*LISTEN" >nul
if errorlevel 1 (
  echo 启动统一邮件中心(3210)...
  start "统一邮件中心" /d "%MAIL_CENTER_DIR%" cmd /k "npx tsx src/index.ts"
) else (
  echo 统一邮件中心(3210) 已在运行，跳过
)

echo.
echo 后端: http://127.0.0.1:8000
echo 前端: http://localhost:5173/
echo 邮件中心: http://127.0.0.1:3210
echo.
echo 请稍等几秒后访问前端地址。
pause
