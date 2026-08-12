@echo off
echo PMWB Windows Service Uninstall (requires admin)
echo.
if not exist "C:\pmwb-logs" mkdir "C:\pmwb-logs"
echo [%date% %time%] uninstall started from %~dp0 >> "C:\pmwb-logs\bat-uninstall-run.log" 2>&1
powershell -ExecutionPolicy Bypass -File "C:\pmwb-scripts\uninstall-windows-services.ps1"
set PS_EXIT=%errorlevel%
echo [%date% %time%] uninstall exited %PS_EXIT% >> "C:\pmwb-logs\bat-uninstall-run.log" 2>&1
if %PS_EXIT% neq 0 (
    echo.
    echo ERROR: uninstall failed with code %PS_EXIT%
    echo Check C:\pmwb-logs\uninstall-services.log
)
