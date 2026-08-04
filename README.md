# 产品经理个人工作台 (PMWB)

> 个人使用的统一工作管理平台，本地运行。覆盖任务中心、需求与交付、运营监控、会议日程、重点工作、知识中心、邮件中心与人员中台。

## 技术栈

- 后端：FastAPI + SQLAlchemy + Alembic + MySQL（端口 8000）
- 前端：Vue 3 + Vite + Element Plus + Pinia + ECharts（端口 5173）
- 人员中台：独立 FastAPI 微服务 `services/master`（端口 8001），组织/人员唯一数据源
- 邮件：统一邮件中心 HTTP API（外部服务，端口 3210）
- 知识库：Obsidian Vault（`D:\项目\知识图谱`，Markdown）
- 浏览器插件：`extension/`（Chrome MV3，页面数据采集回填）

## 已实现模块

菜单顺序即下表顺序，与 `frontend/src/router/index.js` 一致。

| 模块 | 路由 | 状态 | 说明 |
|------|------|------|------|
| 首页看板 | `/dashboard` | ✅ | 实时动态、核心工作区（需求概览/智能优先级待办/重点工作进度）、模块概览（人员中台/知识中心/邮件中心）；ECharts 图表 |
| 任务中心 | `/task-center` | ✅ | 聚合 6 类待办（个人待办/运营问题/开发工单/会议行动项/重点工作/需求催办），支持深链跳来源模块编辑、一键督办邮件 |
| 需求与交付 | `/requirement-delivery` | ✅ | 需求采集→团队评估→DDD 用户故事→生成需求分析说明书 docx；附件上传/下载/删除，全部真实落盘 |
| 运营监控 | `/operation/*` | ✅ | 总览 + BUG管理/数据异常/生产问题/临时交办/热点投诉 五类工单，结果反馈支持附件；生产监控页占位（建设中） |
| 会议日程 | `/meeting/*` | ✅ | 会议列表（议题、背景说明、参会人、纪要必填标记、纪要邮件）+ 行动项子页（跨会议查询、状态切换、一键督办） |
| 个人待办 | `/todo` | ✅ | 待办 CRUD、优先级、截止日期、超期标记 |
| 重点工作 | `/key-works` | ✅ | 总部试点/年度任务/专题工作全周期：目标、验收标准、里程碑、分工、月/周计划、进展、成员待办、交付物（落 Obsidian `09-重点工作`） |
| 人员中台 | `/basic-data` | ✅ | 组织架构与人员管理（代理 8001），全项目选人/收件人解析的唯一数据源 |
| 知识中心 | `/knowledge-center/*` | ✅ | 知识库、产品圣经、知识沉淀、SQL 脚本库 |
| 邮件中心 | `/mail-center/*` | ✅ | 代理统一邮件中心：发送日志（合并展示）、账号、通讯录、分组、模板；通讯录只读复用人员中台 |

隐藏路由（保留深链兼容，不出现在菜单）：`/reminder-center`、`/mail-records`、`/requirement`、`/ticket`、`/requirement-group`。

## 目录结构

```
.
├── backend/              # 主后端（FastAPI, 8000）
│   ├── main.py           # 应用入口，注册 21 个路由模块
│   ├── core/             # 配置、异常、统一响应、docx 转换
│   ├── db/               # SQLAlchemy 模型（28 张表）与连接
│   ├── routers/          # API 路由（health/dashboard/task_center/...）
│   ├── schemas/          # Pydantic 模型
│   ├── services/         # 业务逻辑
│   ├── utils/            # dateflags(逾期判据)/email/master_service/obsidian 等
│   ├── alembic/          # 数据库迁移（23 个版本）
│   ├── templates/        # 需求分析说明书.docx 模板
│   ├── tests/            # pytest（20 个测试文件）
│   └── scripts/          # 开发脚本、数据回填、种子数据
├── services/
│   └── master/           # 人员中台微服务（FastAPI, 8001，独立 alembic）
├── frontend/             # 前端（Vue3 + Vite, 5173）
│   ├── src/api/          # API 封装（17 个模块，baseURL=/api/v1）
│   ├── src/components/   # Charts / Common / Layout
│   ├── src/composables/  # useDrawerDraft（抽屉草稿）、useStaffAdmin
│   └── src/views/        # 页面视图（24 个 + mail 子目录）
├── extension/            # Chrome 浏览器插件（MV3）
├── prototype/            # 静态页面原型（HTML）
├── docs/                 # 需求规格、设计与协同开发规范
├── scripts/              # 启动看门狗与运维脚本（镜像自 C:\pmwb-scripts）
├── .workbuddy/           # 任务总表、审查记录、每日日志、自动化
├── .env.example          # 环境变量模板
└── README.md
```

## 环境要求

- Python 3.11+
- Node.js 18+
- MySQL 5.7+（含既有 `sent_emails` 表，6000+ 条需求催办数据）

## 启动方式

### 方式一：看门狗常驻保活（推荐，日常使用）

桌面双击 `启动PMWB.bat`，运行 `C:\pmwb-scripts\pmwb-keeper.py`（源码镜像在 `scripts/pmwb-keeper.py`）。
看门狗每 15 秒检查 5 个端口，DOWN 即自动拉起：

| 端口 | 服务 | 依赖 |
|------|------|------|
| 3306 | MySQL | — |
| 8000 | 主后端 | 等 3306 就绪 |
| 8001 | 人员中台 Master | 等 3306 就绪 |
| 5173 | 前端 Vite | — |
| 3210 | 统一邮件中心 | — |

- 一键重启：桌面 `重启PMWB.bat`（终止前后端+MySQL+Master 与旧看门狗，再后台重新拉起；邮件中心 3210 不动）
- 一次性拉起（不常驻）：`python scripts/pmwb-keeper.py --once`

> ⚠️ 开机自启铁律：Startup 的 `pmwb-autostart.vbs` 必须用 `cmd /c "<python.exe>" "<keeper.py>"`。
> **不能用 `pythonw` 或隐藏窗口方式直接拉 python.exe** —— 那样 `mysqld --console` 会静默失败，数据库起不来。
> MySQL 控制台模式下有父引导 + 子工作两个 `mysqld.exe` 进程，属正常现象。

### 方式二：手动启动

```bash
# 后端
cd backend && venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload

# 人员中台
cd services/master && venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001

# 前端
cd frontend && npm run dev
```

启动后访问：
- 前端 http://127.0.0.1:5173/
- 后端健康检查 http://127.0.0.1:8000/api/v1/health
- API 文档 http://127.0.0.1:8000/docs

## 配置

复制 `.env.example` 到 `backend\.env` 并填写：

```env
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=<必填，无默认值>
DB_NAME=yxtyg_db
SECRET_KEY=<必填，随机长字符串>
EMAIL_CENTER_URL=http://localhost:3210
MASTER_SERVICE_URL=http://localhost:8001
OBSIDIAN_VAULT_PATH=D:\项目\知识图谱
```

> ⚠️ `DB_PASSWORD` 与 `SECRET_KEY` 为**必填项**，代码已移除硬编码默认值，缺失会启动报错。`DEBUG` 默认 False。

执行迁移（改动 SQLAlchemy 模型后必须先迁移再起后端，否则报 1054 Unknown column）：

```bash
cd backend && venv\Scripts\alembic.exe upgrade head
```

## 主要 API

统一前缀 `/api/v1`，统一响应体 `{code, message, data}`（`code===0` 为成功）。

| 模块 | 路径 | 说明 |
|------|------|------|
| 健康检查 | `/health` | 服务状态 |
| 首页看板 | `/dashboard` | 聚合统计（KPI/趋势/模块卡） |
| 任务中心 | `/task-center` | `/stats`、`/tasks`、`/tasks/{source}/{source_id}`、`/resolve-contacts`、`/send` |
| 需求管理 | `/requirements` | 列表/统计/跟踪/评估 |
| 需求交付 | `/requirements/{req_id}/delivery` | 附件 CRUD、用户故事生成、说明书 docx 生成 |
| 用户故事 | `/user-stories` | DDD 用户故事规则与生成 |
| 开发工单 | `/dev-tickets` | 六阶段生命周期、变更日志、交付物 |
| 业务运营监控 | `/operation` | 问题 CRUD + 统计 + 结果反馈附件 |
| 会议管理 | `/meetings` | 会议、议题（含背景说明）、参会人、纪要邮件 |
| 会议行动项 | `/meeting-actions` | 跨会议查询、状态更新、完整编辑 |
| 个人待办 | `/todos` | 待办 CRUD + 统计 |
| 重点工作 | `/key-works` | 主表 + 子表（进展/成员待办/里程碑/成员/月周计划）+ 交付物 |
| 人员中台 | `/basic-data` | 组织/人员/角色 CRUD 与 options（代理 8001） |
| 邮件中心 | `/mail-center` | 27 个代理端点（日志/账号/通讯录/分组/模板） |
| 邮件催办 | `/reminders` | 发送催办 + 记录查询 |
| 邮件督办 | `/supervise` | `/ticket`、`/action` 一键督办 |
| 知识库 | `/knowledge` | 知识条目 + Markdown |
| 产品圣经 | `/product-bible` | 产品知识树检索 |
| SQL 脚本库 | `/sql-scripts` | 脚本 CRUD |
| Obsidian 联动 | `/obsidian` | 笔记读写与链接 |
| 插件接入 | `/plugin` | 浏览器插件数据回填 |

## 开发规范

**铁律：禁止在 main 主干直接开发**，所有改动走 feature 分支 → 审查 → 合版。

- 完整规范：`docs/COLLABORATIVE_DEV_WORKFLOW.md`
- 任务总表：`.workbuddy/tasks/TASKS.md`；任务 Spec：`.workbuddy/tasks/<task-id>.md`
- 审查反馈：`.workbuddy/reviews/<task-id>-R<N>.md`
- 分支命名：`feature/<task-id>-<kebab-desc>`
- 质量门禁：pytest 绿 + vitest 绿 + `vite build` 干净 + 浏览器冒烟 + 代码审查 + 影响面 Grep

### 关键约定（高频坑）

- **API**：`request.js` 的 `baseURL='/api/v1'`，api 文件用相对路径（如 `/requirements`）；拦截器已解包 `data.data`，禁止二次解包
- **响应**：`success()` 用 `message=`（不是 `msg=`），否则 TypeError → 500
- **时区**：中国 UTC+8，统计用 `datetime.now(timezone(timedelta(hours=8)))`；库表 UTC 存、展示 +8h
- **跨方言**：SQLite 内存库跑测试，禁用 `cast(col, Date)`（SQLite 走 numeric affinity 会失效），改用 naive datetime 区间比较
- **日期空值**：前端传 `""` 会触发 Pydantic `Optional[date]` 422，Update schema 需加 `@field_validator(mode="before")` 把 `""` 转 `None`
- **图标引用**：数组字面量里的 `icon: Xxx` 会立即求值，漏 import 直接白屏且 Rollup 不报错——浏览器冒烟是必过项
- **菜单隐藏**：`MainLayout.vue` 的 `menuItems` 必须 `.filter(c => !c.meta?.hidden)` 才真正隐藏
- **公共能力**：人员信息统一走人员中台（`master_service.py` / `StaffSelect` 组件），邮件统一走邮件中心，禁止各模块自建人员表或硬编码收件人

## 测试

```bash
cd backend && venv\Scripts\python.exe -m pytest -q     # 116 passed
cd frontend && npm run test                             # vitest 7/7
cd frontend && npm run build                            # 构建须干净
```

> 已知：`test_basic_data` / `test_product_bible` 中 3 个用例依赖真实运行的人员中台 8001 与真实库数据，本机环境下会失败，与代码改动无关（已用纯净 main worktree 对照验证）。

## 文档索引

| 文档 | 状态 | 说明 |
| :--- | :--- | :--- |
| `docs/需求规格说明书.md` | ✅ 现行 v0.7 | 系统全貌：11 个模块、28 张表、架构与服务拓扑 |
| `docs/COLLABORATIVE_DEV_WORKFLOW.md` | ✅ 现行 v1.1 | 多 AI 协同开发规范（分支/审查/合版） |
| `docs/开发工单模块设计.md` | ✅ 现行 | 模块3 详细设计（状态流、表结构、归档规则） |
| `.workbuddy/tasks/TASKS.md` | ✅ 现行 | 任务总表与批次记录 |
| `docs/architecture_review_2026-07-25.md` | 📌 历史快照 | 架构审查报告，主要整改项已落地 |
| `docs/ui-redesign-proposals.md` | 📌 提案 | 表单 UI 重设计，仅局部采纳 |
| `docs/开发计划与worktree并行开发方案.md` | 🗄️ 已归档 | worktree 并行方式已弃用 |

---

_个人使用，持续迭代中。_
