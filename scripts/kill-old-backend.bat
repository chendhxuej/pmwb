@echo off
chcp 65001 >nul 2>&1
echo ============================================
echo  停止占用 8000 端口的旧 PMWB 后端进程
echo  （服务已卸载，但残留进程仍在跑旧代码）
echo ============================================
echo.
for /f "tokens=5" %%a in ('netstat -ano -p tcp ^| findstr "LISTENING" ^| findstr ":8000"') do (
    echo   终止占用 8000 的 PID %%a
    taskkill /F /PID %%a >nul 2>&1
    if errorlevel 1 (echo     终止失败，可能需要更高权限) else (echo     已终止)
)
echo.
echo 旧进程已清理。看门狗会于数秒内自动拉起最新后端。
echo 稍后可让 Vicky 验证页面是否恢复。
echo.
pause
