# 产品经理个人工作台 (PMWB)

> 个人使用的统一工作管理平台，覆盖需求管理、开发工单跟踪、业务运营监控、会议管理、知识库与待办中心。

## 技术栈

- 后端：FastAPI + SQLAlchemy + Alembic + MySQL
- 前端：Vue 3 + Vite + Element Plus + Pinia
- 邮件：统一邮件中心 HTTP API
- 知识库：Obsidian Vault (Markdown)

## 目录结构

```
.
├── backend/          # 后端代码
├── frontend/         # 前端代码
├── docs/             # 需求与设计文档
├── scripts/          # 工具脚本
├── sql/              # 数据库脚本
├── .env.example      # 环境变量模板
└── README.md
```

## 快速启动

### 后端

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

## 开发分支

使用 Git Worktree 进行并行开发，详见 `docs/开发计划与worktree并行开发方案.md`。

---

_个人使用，持续迭代中。_
