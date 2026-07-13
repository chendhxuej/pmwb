@echo off
chcp 65001 >nul
cd /d "D:\项目\个人工作台系统\frontend"
"C:\Users\chend\.workbuddy\binaries\node\versions\22.22.2\node.exe" "C:\Users\chend\.workbuddy\binaries\node\versions\22.22.2\node_modules\npm\bin\npm-cli.js" run dev
pause
