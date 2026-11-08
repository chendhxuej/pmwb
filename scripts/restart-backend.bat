@echo off
chcp 65001 >nul 2>&1
title 重启 PMWB 后端（加载新接口）
echo ============================================
echo  重启 PMWB-Backend 服务，加载「从邮件导入」新接口
echo  ⚠ 必须右键「以管理员身份运行」，否则停不掉服务
echo ============================================
echo.
net stop PMWB-Backend
if errorlevel 1 (
    echo [失败] 停止服务失败：请确认是用管理员身份运行的。
    pause
    exit /b 1
)
net start PMWB-Backend
if errorlevel 1 (
    echo [失败] 启动服务失败：看 C:\pmwb-logs 或服务日志。
    pause
    exit /b 1
)
echo.
echo 等待后端就绪 ...
timeout /t 8 /nobreak >nul
echo.
echo 自检：新接口是否上线
curl -s -o nul -w "health=%%{http_code}\n" http://127.0.0.1:8000/api/v1/health
rem 用 HTTP 码判断：401=接口存在且要求鉴权，404=接口不存在
for /f %%c in ('curl -s -o nul -w "%%{http_code}" http://127.0.0.1:8000/api/v1/key-works/mail-import/status') do set MI=%%c
if "%MI%"=="401" (
    echo [OK] mail-import 接口已加载，可以去「重点工作 - 从邮件导入」了
) else if "%MI%"=="200" (
    echo [OK] mail-import 接口已加载，可以去「重点工作 - 从邮件导入」了
) else (
    echo [警告] 接口返回 %MI%，未按预期上线，请看后端日志排查
)
echo.
pause
