@echo off
chcp 65001 >nul
echo 正在启动产品经理个人工作台...
echo.

start "PMWB Backend" "D:\项目\个人工作台系统\backend\scripts\run_dev.bat"
timeout /t 3 /nobreak >nul
start "PMWB Frontend" "D:\项目\个人工作台系统\frontend\scripts\run_dev.bat"

echo.
echo 后端: http://127.0.0.1:8000
echo 前端: http://localhost:5173/
echo.
echo 请稍等几秒后访问前端地址。
pause
