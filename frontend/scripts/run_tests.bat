@echo off
chcp 65001 >nul
REM 前端测试运行脚本
pushd "%~dp0\.."
npm run test
if %errorlevel% neq 0 (
  echo 前端测试未全部通过
  exit /b 1
)
popd
