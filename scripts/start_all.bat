@echo off
setlocal enabledelayedexpansion

echo [PMWB] start_all : checking services...

call :ensure_mysql
call :ensure_backend
call :ensure_frontend
call :ensure_mail

echo [PMWB] all done.
goto :eof

:ensure_mysql
for /f "tokens=*" %%a in ('netstat -ano 2^>nul ^| findstr /C:":3306 "') do goto :mysql_running
echo [PMWB] MySQL not running, starting...
start "MySQL" /min "C:/mysql/mysql-8.0.46-winx64/bin/mysqld.exe" --defaults-file="C:/mysql/mysql-8.0.46-winx64/my.ini"
set /a T=0
:mysql_wait
set /a T+=1
if !T! GTR 40 ( echo [PMWB] ERROR: MySQL failed to start within 40s & goto :eof )
netstat -ano 2^>nul | findstr /C:":3306 " >nul && goto :mysql_running
timeout /t 1 >nul
goto :mysql_wait
:mysql_running
echo [PMWB] MySQL OK
goto :eof

:ensure_backend
for /f "tokens=*" %%a in ('netstat -ano 2^>nul ^| findstr /C:":8000 "') do goto :be_running
echo [PMWB] starting backend...
start "PMWB-Backend" /min /D "D:/项目/个人工作台系统/backend" "D:/项目/个人工作台系统/backend/venv/Scripts/python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8000
goto :eof
:be_running
echo [PMWB] backend already running
goto :eof

:ensure_frontend
for /f "tokens=*" %%a in ('netstat -ano 2^>nul ^| findstr /C:":5173 "') do goto :fe_running
echo [PMWB] starting frontend...
start "PMWB-Frontend" /min /D "D:/项目/个人工作台系统/frontend" "C:/Users/chend/.workbuddy/binaries/node/versions/22.22.2/node.exe" node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5173
goto :eof
:fe_running
echo [PMWB] frontend already running
goto :eof

:ensure_mail
for /f "tokens=*" %%a in ('netstat -ano 2^>nul ^| findstr /C:":3210 "') do goto :mail_running
echo [PMWB] starting mail center...
start "PMWB-Mail" /min /D "D:/项目/个人工作台系统/email-manager" "C:/Users/chend/.workbuddy/binaries/node/versions/22.22.2/node.exe" node_modules/.bin/tsx src/index.ts
goto :eof
:mail_running
echo [PMWB] mail center already running
goto :eof
