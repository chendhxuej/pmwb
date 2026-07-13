@echo off
chcp 65001 >nul
cd /d "D:\项目\个人工作台系统\backend"
"D:\项目\个人工作台系统\backend\venv\Scripts\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
pause
