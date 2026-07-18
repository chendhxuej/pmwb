@echo off
echo PMWB Windows Service Install (requires admin)
echo.
if not exist "C:\pmwb-logs" mkdir "C:\pmwb-logs"
echo [%date% %time%] install started from %~dp0 >> "C:\pmwb-logs\bat-run.log" 2>&1
powershell -ExecutionPolicy Bypass -File "C:\pmwb-scripts\install-windows-services.ps1"
set PS_EXIT=%errorlevel%
echo [%date% %time%] install exited %PS_EXIT% >> "C:\pmwb-logs\bat-run.log" 2>&1
if %PS_EXIT% neq 0 (
    echo.
    echo ERROR: install failed with code %PS_EXIT%
    echo Check C:\pmwb-logs\install-services.log
)
