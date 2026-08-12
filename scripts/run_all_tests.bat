@echo off
chcp 65001 >nul
REM 运行全部测试（后端 + 前端）
pushd "%~dp0\.."

echo ===== 运行后端测试 =====
call backend\scripts\run_tests.bat
if %errorlevel% neq 0 (
  echo 后端测试失败，停止执行
  popd
  exit /b 1
)

echo.
echo ===== 运行前端测试 =====
call frontend\scripts\run_tests.bat
if %errorlevel% neq 0 (
  echo 前端测试失败，停止执行
  popd
  exit /b 1
)

echo.
echo ===== 全部测试通过 =====
popd
