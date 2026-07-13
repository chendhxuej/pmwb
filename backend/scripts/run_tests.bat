@echo off
chcp 65001 >nul
REM 后端测试运行脚本
pushd "%~dp0\.."
venv\Scripts\python.exe -m pytest tests\ -v
if %errorlevel% neq 0 (
  echo 后端测试未全部通过
  exit /b 1
)
popd
