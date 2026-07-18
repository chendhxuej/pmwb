@echo off
cd /d "D:\项目\个人工作台系统\backend"
REM 先同步库表结构，避免模型与库表不一致导致新列查询 500
"D:\项目\个人工作台系统\backend\venv\Scripts\python.exe" -m alembic upgrade head
"D:\项目\个人工作台系统\backend\venv\Scripts\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
