# 产品经理个人工作台 (PMWB)

> 个人使用的统一工作管理平台，覆盖需求管理、开发工单跟踪、业务运营监控、会议管理、知识库与待办中心。

## 技术栈

- 后端：FastAPI + SQLAlchemy + Alembic + MySQL
- 前端：Vue 3 + Vite + Element Plus + Pinia
- 邮件：统一邮件中心 HTTP API
- 知识库：Obsidian Vault (Markdown)

## 已实现模块

| 模块 | 状态 | 说明 |
|------|------|------|
| 首页看板 | ✅ | 聚合待办、会议、运营问题、知识库统计数据 |
| 业务运营监控 | ✅ | 问题录入、分类、状态跟踪、统计 |
| 会议管理 | ✅ | 会议记录、参会人、行动项 |
| 知识库 | ✅ | 条目索引、Obsidian Markdown 归档 |
| 待办中心 | ✅ | 待办任务、优先级、截止日期、超期提醒 |
| 需求管理 | ✅ | 聚合 sent_emails + pmwb_requirement_ext，跟踪/催办；需求与交付工作流（采集→团队评估→DDD 用户故事→生成需求分析说明书 docx，全部真实后端落盘） |
| 开发工单 | ✅ | 六阶段生命周期、变更日志、交付物归档 |
| 统一邮件催办 | ✅ | 对接统一邮件中心，发送催办并记录发送状态 |
| 重点工作 | ✅ | 总部试点/年度任务/专题工作三类全周期管理：基本信息、工作目标、验收标准、里程碑、团队分工、月/周计划、工作进展、成员待办、交付物归档（落 Obsidian 09-重点工作） |

## 目录结构

```
.
├── backend/          # 后端代码
│   ├── app/          # 应用逻辑
│   ├── core/         # 配置、异常、响应
│   ├── db/           # 数据库模型与连接
│   ├── routers/      # API 路由
│   ├── schemas/      # Pydantic 模型
│   ├── services/     # 业务逻辑
│   ├── utils/        # 工具函数
│   ├── alembic/      # 数据库迁移
│   └── scripts/      # 启动脚本
├── frontend/         # 前端代码
│   ├── src/api/      # API 封装
│   ├── src/components/ # 通用组件
│   ├── src/views/    # 页面视图
│   └── scripts/      # 启动脚本
├── docs/             # 需求与设计文档
├── scripts/          # 一键启动脚本
├── sql/              # 数据库脚本
├── .env.example      # 环境变量模板
└── README.md
```

## 环境要求

- Python 3.11+
- Node.js 18+
- MySQL 5.7+（已包含现有 `sent_emails` 表）

## 快速启动

### 方式一：一键启动（推荐）

双击运行：

```
scripts\start_all.bat
```

该脚本会依次拉起 **MySQL(3306) → 后端(8000) → 前端(5173) → 统一邮件中心(3210)**，端口已监听则自动跳过。

> 说明：本机 MySQL80 Windows 服务已损坏（`net start` 报 2186），脚本改用进程直拉 mysqld（免管理员）。桌面另有一键脚本 `pmwb-start.bat` 功能相同，并额外支持注册「登录 Windows 自动启动」。

启动后访问：
- 前端：http://127.0.0.1:5173/ （或 http://localhost:5173/）
- 后端 API：http://127.0.0.1:8000/api/v1/health

### 方式二：手动启动

#### 后端

```bash
cd backend
venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

或运行脚本：

```
backend\scripts\run_dev.bat
```

#### 前端

```bash
cd frontend
npm run dev
```

或运行脚本：

```
frontend\scripts\run_dev.bat
```

## 数据库配置

复制 `.env.example` 到 `backend\.env`，并修改数据库连接信息：

```env
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=123456
DB_NAME=yxtyg_db
DB_CHARSET=utf8mb4
```

执行迁移：

```bash
cd backend
venv\Scripts\alembic.exe upgrade head
```

## 主要 API

| 模块 | 路径前缀 | 说明 |
|------|---------|------|
| 健康检查 | `/api/v1/health` | 服务状态 |
| 业务运营监控 | `/api/v1/operation` | 问题 CRUD + 统计 |
| 会议管理 | `/api/v1/meetings` | 会议 CRUD |
| 知识库 | `/api/v1/knowledge` | 知识条目 + Markdown 内容 |
| 待办中心 | `/api/v1/todos` | 待办 CRUD + 统计 |
| 首页看板 | `/api/v1/dashboard` | 聚合数据 |
| 需求管理 | `/api/v1/requirements` | 需求列表/统计/跟踪 |
| 需求交付 | `/api/v1/requirements/{req_id}/delivery` | 自动建文件夹、附件上传/列表/下载/删除、DDD 用户故事生成、需求分析说明书 docx 生成 |
| 开发工单 | `/api/v1/dev-tickets` | 工单 CRUD + 状态流转 |
| 统一邮件催办 | `/api/v1/reminders` | 发送催办 + 记录查询 |
| 重点工作 | `/api/v1/key-works` | 列表/统计/详情/CRUD + 子表（进展/成员待办/里程碑/成员/月周计划）+ 交付物上传下载删除 |

## 开发分支

使用 Git Worktree 进行并行开发，详见 `docs/开发计划与worktree并行开发方案.md`。

---

_个人使用，持续迭代中。_
