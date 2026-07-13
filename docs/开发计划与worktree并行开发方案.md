# 产品经理个人工作台 — 开发计划与 Worktree 并行开发方案

> 版本：v1.0  
> 日期：2026-07-13  
> 开发方法：基于 Superpowers 标准化开发方法（模块化、分层解耦、标准化、可复用）

---

## 一、总体开发策略

### 1.1 原则

本开发计划遵循以下原则：

- **先框架、后模块**：先搭建统一技术框架、数据库模型、通用组件，再并行开发业务模块。
- **基础优先、业务并行**：基础框架阶段串行推进；业务模块阶段多个模块并行开发，互不阻塞。
- **看板与任务中心最后做**：首页看板和待办中心依赖其他模块的数据沉淀，放在最后实现，确保数据口径统一。
- **Worktree 并行开发**：使用 Git Worktree 为每个开发任务维护独立工作目录，避免频繁切换分支，提升并行开发效率。
- **小步快跑、持续集成**：每个模块独立开发、独立测试，完成后合并到主干，逐步集成。

### 1.2 开发阶段划分

```
Phase 0: 基础框架搭建（1-2 周）
    ├── 项目目录与工程结构
    ├── 数据库模型与迁移脚本
    ├── 后端 FastAPI 基础框架
    ├── 前端 Vue3 + Element Plus 基础框架
    └── 通用组件与基础能力

Phase 1: 业务模块并行开发（2-3 周）
    ├── 业务运营监控模块
    ├── 会议管理模块
    └── 知识库模块

Phase 2: 收尾模块开发（1-2 周）
    ├── 首页可视化看板
    └── 待办中心

Phase 3: 集成测试与部署（1 周）
    ├── 集成测试
    ├── 缺陷修复
    └── 部署脚本与本地运行配置
```

### 1.3 模块优先级

| 优先级 | 模块 | 说明 |
| :--- | :--- | :--- |
| P0 | 基础框架 | 所有模块依赖 |
| P1 | 业务运营监控 | 当前重点工作之一（跨省宽带、CIP00066、LAN 网关等） |
| P1 | 会议管理 | 高频使用，沉淀会议纪要 |
| P1 | 知识库 | 长期价值高，与 Obsidian 联动 |
| P2 | 首页可视化看板 | 依赖其他模块数据，最后做 |
| P2 | 待办中心 | 依赖其他模块关联，最后做 |

---

## 二、Git Worktree 并行开发方案

### 2.1 为什么使用 Worktree

Git Worktree 允许同一个仓库同时拥有多个工作目录，每个目录关联不同分支。相比单目录切换分支：

- **避免上下文切换**：开发业务模块 A 时，不需要 stash 模块 B 的改动。
- **并行调试**：每个模块可以在独立目录运行、测试。
- **独立评审**：每个 worktree 对应一个清晰分支，便于 diff 和 merge。
- **稳定主干**：`main` 工作目录始终保持可运行版本，不受影响。

### 2.2 仓库与 Worktree 目录结构

主仓库目录：

```
D:\项目\个人工作台系统\
├── .git/                      # Git 仓库根
├── docs/                      # 需求文档、设计文档
├── backend/                   # 后端代码（主工作树）
├── frontend/                  # 前端代码（主工作树）
├── scripts/                   # 脚本工具
├── docker-compose.yml         # 本地编排（可选）
├── README.md
└── ...
```

Worktree 目录（建议放在主仓库同级目录，避免嵌套）：

```
D:\项目\个人工作台系统-worktree\
├── main\                       # 主干分支，稳定可运行版本
├── feature-db-schema\          # 数据库模型与迁移
├── feature-backend-base\        # 后端 FastAPI 基础框架
├── feature-frontend-base\       # 前端 Vue3 基础框架
├── feature-common-components\   # 通用组件与基础能力
├── feature-module-operation\    # 业务运营监控模块
├── feature-module-meeting\     # 会议管理模块
├── feature-module-knowledge\   # 知识库模块
├── feature-dashboard\           # 首页可视化看板
├── feature-todo-center\         # 待办中心
└── release-integration\         # 集成测试与发布
```

### 2.3 分支策略

| 分支 | 类型 | 用途 |
| :--- | :--- | :--- |
| `main` | 长期 | 稳定主干，始终保持可运行 |
| `feature-db-schema` | 短期 | 数据库模型与迁移脚本 |
| `feature-backend-base` | 短期 | 后端基础框架 |
| `feature-frontend-base` | 短期 | 前端基础框架 |
| `feature-common-components` | 短期 | 通用组件与基础能力 |
| `feature-module-operation` | 短期 | 业务运营监控模块 |
| `feature-module-meeting` | 短期 | 会议管理模块 |
| `feature-module-knowledge` | 短期 | 知识库模块 |
| `feature-dashboard` | 短期 | 首页可视化看板 |
| `feature-todo-center` | 短期 | 待办中心 |
| `release/integration` | 短期 | 集成测试与发布准备 |

### 2.4 Worktree 创建命令

初始化 worktree（在已初始化的 Git 仓库中执行）：

```bash
# 1. 确保主仓库已初始化
cd "D:\项目\个人工作台系统"
git init
git add .
git commit -m "chore: initial project setup"

# 2. 创建主干 worktree
git branch main
git worktree add "D:\项目\个人工作台系统-worktree\main" main

# 3. 创建各 feature 分支及 worktree
git branch feature-db-schema
git worktree add "D:\项目\个人工作台系统-worktree\feature-db-schema" feature-db-schema

git branch feature-backend-base
git worktree add "D:\项目\个人工作台系统-worktree\feature-backend-base" feature-backend-base

git branch feature-frontend-base
git worktree add "D:\项目\个人工作台系统-worktree\feature-frontend-base" feature-frontend-base

git branch feature-common-components
git worktree add "D:\项目\个人工作台系统-worktree\feature-common-components" feature-common-components

git branch feature-module-operation
git worktree add "D:\项目\个人工作台系统-worktree\feature-module-operation" feature-module-operation

git branch feature-module-meeting
git worktree add "D:\项目\个人工作台系统-worktree\feature-module-meeting" feature-module-meeting

git branch feature-module-knowledge
git worktree add "D:\项目\个人工作台系统-worktree\feature-module-knowledge" feature-module-knowledge

git branch feature-dashboard
git worktree add "D:\项目\个人工作台系统-worktree\feature-dashboard" feature-dashboard

git branch feature-todo-center
git worktree add "D:\项目\个人工作台系统-worktree\feature-todo-center" feature-todo-center

git branch release/integration
git worktree add "D:\项目\个人工作台系统-worktree\release-integration" release/integration
```

### 2.5 代码合并流程

```
feature-xxx 分支开发完成
        │
        ▼
  自测通过，提交 commit
        │
        ▼
  发起 Pull Request / 手动合并到 main
        │
        ▼
  合并后，其他 feature 分支 rebase 或 merge main 同步最新代码
        │
        ▼
  继续开发或关闭该 worktree
```

### 2.6 Worktree 清理

模块开发完成并合并后，清理对应 worktree：

```bash
# 移除 worktree（保留分支）
git worktree remove "D:\项目\个人工作台系统-worktree\feature-module-operation"

# 如果分支已合并，可删除分支
git branch -d feature-module-operation
```

---

## 三、任务拆分与并行安排

### 3.1 任务总览

| 任务ID | 任务名称 | 所属阶段 | 优先级 | Worktree | 阻塞关系 | 预计工期 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | 搭建项目基础框架与目录结构 | Phase 0 | P0 | main | 无 | 0.5 天 |
| T2 | 设计并实现数据库基础模型与迁移 | Phase 0 | P0 | feature-db-schema | T1 | 1 天 |
| T3 | 搭建后端 FastAPI 基础框架 | Phase 0 | P0 | feature-backend-base | T1 | 1 天 |
| T4 | 搭建前端 Vue3 + Element Plus 基础框架 | Phase 0 | P0 | feature-frontend-base | T1 | 1 天 |
| T5 | 实现通用基础能力 | Phase 0 | P0 | feature-common-components | T3, T4 | 2 天 |
| T6 | 开发业务运营监控模块 | Phase 1 | P1 | feature-module-operation | T2, T5 | 3 天 |
| T7 | 开发会议管理模块 | Phase 1 | P1 | feature-module-meeting | T2, T5 | 3 天 |
| T8 | 开发知识库模块 | Phase 1 | P1 | feature-module-knowledge | T2, T5 | 3 天 |
| T9 | 开发首页可视化看板 | Phase 2 | P2 | feature-dashboard | T6, T7, T8 | 2 天 |
| T10 | 开发待办中心 | Phase 2 | P2 | feature-todo-center | T6, T7, T8 | 2 天 |
| T11 | 系统集成测试与缺陷修复 | Phase 3 | P1 | release-integration | T9, T10 | 3 天 |
| T12 | 部署脚本与本地运行配置 | Phase 3 | P1 | release-integration | T11 | 1 天 |

### 3.2 并行节奏

```
Week 1: Phase 0 基础框架
    Day 1:  T1  项目目录结构
    Day 2:  T2  数据库模型  │  T3  后端基础  │  T4  前端基础  （并行）
    Day 3-4: T5 通用基础能力
    Day 5:  合并 Phase 0 到 main，代码评审

Week 2-3: Phase 1 业务模块并行
    T6 业务运营监控  │  T7 会议管理  │  T8 知识库  （三个 worktree 并行）
    每 2-3 天同步一次 main 更新

Week 4: Phase 2 收尾模块并行
    T9 首页可视化看板  │  T10 待办中心  （两个 worktree 并行）

Week 5: Phase 3 集成与部署
    T11 集成测试与缺陷修复
    T12 部署脚本与本地运行配置
```

---

## 四、各任务详细说明

### T1：搭建项目基础框架与目录结构

**目标**：建立统一工程目录和规范。

**输出**：

```
D:\项目\个人工作台系统\
├── .git/                      # Git 仓库
├── .gitignore                 # 忽略 node_modules, venv, __pycache__ 等
├── backend/                   # 后端根目录
│   ├── app/
│   ├── core/                  # 配置、日志、异常
│   ├── db/                    # 数据库连接、迁移
│   ├── routers/               # API 路由
│   ├── schemas/               # Pydantic 模型
│   ├── services/              # 业务逻辑
│   ├── utils/                 # 工具函数
│   ├── tests/                 # 单元测试
│   ├── main.py                # 入口
│   ├── requirements.txt
│   └── alembic/               # 迁移工具
├── frontend/                  # 前端根目录
│   ├── src/
│   ├── public/
│   ├── package.json
│   ├── vite.config.js
│   └── README.md
├── scripts/                   # 工具脚本
├── docs/                      # 文档
├── docker-compose.yml         # 可选
└── README.md
```

**验收标准**：
- 目录结构清晰，前后端分离
- README 包含项目简介、启动方式、技术栈
- `.gitignore` 配置完整

---

### T2：设计并实现数据库基础模型与迁移

**目标**：根据需求文档建立数据库表结构，使用 Alembic 管理迁移。

**输出**：
- 所有 `pmwb_*` 表的 SQLAlchemy 模型
- Alembic 初始迁移脚本
- 数据字典文档

**涉及表**：
- `pmwb_requirement_ext`
- `pmwb_dev_ticket`
- `pmwb_dev_deliverable`
- `pmwb_dev_ticket_log`
- `pmwb_todo`
- `pmwb_operation_issue`
- `pmwb_meeting`
- `pmwb_meeting_attendee`
- `pmwb_meeting_action`
- `pmwb_knowledge_item`

**验收标准**：
- 所有表能正常创建
- 外键关系正确
- 索引覆盖常用查询字段
- 迁移脚本可回滚

---

### T3：搭建后端 FastAPI 基础框架

**目标**：建立可运行的后端服务框架。

**输出**：
- FastAPI 应用入口 `main.py`
- 统一配置管理（`.env` + `pydantic-settings`）
- 数据库连接（SQLAlchemy + MySQL）
- 统一响应结构（成功/失败）
- 全局异常处理
- 日志记录
- 路由注册机制
- 健康检查接口 `/health`

**验收标准**：
- `uvicorn main:app --reload` 可启动
- 访问 `/docs` 可看到 Swagger 文档
- 健康检查接口返回正常
- 配置项从环境变量读取

---

### T4：搭建前端 Vue3 + Element Plus 基础框架

**目标**：建立可运行的前端工程。

**输出**：
- Vue 3 + Vite 项目结构
- Element Plus 组件库集成
- Vue Router 路由配置
- Pinia 状态管理
- Axios 封装（含请求拦截、错误处理）
- 基础布局（Header / Sidebar / Main Content）
- 404 页面
- 主题色配置

**验收标准**：
- `npm run dev` 可启动
- 页面能正常显示基础布局
- Element Plus 组件可用
- 路由切换正常

---

### T5：实现通用基础能力

**目标**：沉淀前后端可复用的通用能力，减少后续模块重复开发。

**后端输出**：
- 通用 CRUD Service 基类
- 统一分页查询模型
- 通用搜索过滤工具
- 文件上传工具（Obsidian 路径归档）
- Markdown 读写工具
- 邮件模板调用工具（统一邮件中心 HTTP 客户端）
- 常用校验器

**前端输出**：
- 通用列表组件（含分页、搜索、排序、操作列）
- 通用表单组件（含校验、提交）
- 通用详情页布局
- 通用状态徽章组件
- 通用日期/时间选择器
- 通用文件上传组件
- 通用确认对话框
- 常用工具函数（日期格式化、状态映射）

**验收标准**：
- 后端通用 Service 可覆盖 80% 的 CRUD 场景
- 前端通用列表组件传入配置即可渲染
- 文件上传能按规则归档到指定路径

---

### T6：开发业务运营监控模块

**目标**：实现运营问题的录入、跟踪、复盘、沉淀。

**后端输出**：
- `pmwb_operation_issue` 表的 CRUD API
- 问题状态流转 API
- 按类型/系统/月份统计接口
- 超期检测逻辑
- 一键生成 Bug 解决方案 / 运维 SOP 接口

**前端输出**：
- 运营问题列表页
- 运营问题详情页
- 问题录入/编辑表单
- 处理记录时间线
- 统计报表页
- 首页运营问题预警卡片

**验收标准**：
- 可完成问题的完整生命周期管理
- 能生成 Obsidian 知识条目
- 超期问题在首页高亮

---

### T7：开发会议管理模块

**目标**：实现会议计划、纪要、行动项管理。

**后端输出**：
- `pmwb_meeting`、`pmwb_meeting_attendee`、`pmwb_meeting_action` CRUD API
- 会议纪要 Markdown 生成接口
- 行动项转待办接口
- 会议提醒接口

**前端输出**：
- 会议列表页（日历视图 + 列表视图）
- 会议创建/编辑表单
- 会议纪要编辑页
- 行动项管理
- 会议详情页

**验收标准**：
- 可创建会议并生成纪要
- 行动项可同步到待办中心
- 会议纪要按规范归档到 Obsidian

---

### T8：开发知识库模块

**目标**：实现知识条目索引、分类、检索、与业务对象关联。

**后端输出**：
- `pmwb_knowledge_item` CRUD API
- 扫描 Obsidian 目录并同步索引接口
- 全文搜索接口
- 按分类/标签统计接口

**前端输出**：
- 知识库列表页
- 知识详情页（Markdown 预览）
- 知识分类导航
- 全文搜索
- 模板创建入口
- 来源关联展示

**验收标准**：
- 能扫描并索引 Obsidian 知识条目
- 支持按关键词搜索
- 知识条目可关联到需求/工单/运营问题/会议

---

### T9：开发首页可视化看板

**目标**：聚合各模块关键数据，提供一目了然的工作总览。

**后端输出**：
- 看板数据聚合接口
- 关键指标计算接口
- 待办/工单/运营问题统计接口
- 趋势数据接口（近 7 天/30 天）

**前端输出**：
- 指标卡片区（需求总数、在途工单、未闭环问题、本周会议）
- 今日待办区
- 超期预警区
- 需求状态分布图表
- 工单进度列表
- 今日会议列表
- 快捷入口区

**验收标准**：
- 首页加载 ≤ 2 秒
- 数据实时或准实时（可接受 5 分钟内缓存）
- 关键指标准确

---

### T10：开发待办中心

**目标**：实现个人待办任务的全面管理。

**后端输出**：
- `pmwb_todo` CRUD API
- 状态变更 API
- 重复任务生成逻辑
- 业务关联查询
- 提醒检测逻辑

**前端输出**：
- 待办列表页
- 待办看板视图（按状态）
- 待办日历视图
- 待办创建/编辑表单
- 重复任务配置
- 业务关联选择器

**验收标准**：
- 可创建、完成、删除待办
- 支持重复任务
- 可关联到需求/工单/运营问题/会议
- 超期待办在首页高亮

---

### T11：系统集成测试与缺陷修复

**目标**：确保各模块集成后功能正常、数据一致。

**输出**：
- 集成测试用例
- 端到端测试脚本
- 缺陷清单与修复记录
- 性能测试（首页加载、列表查询）
- 数据一致性检查（MySQL 与 Obsidian 双写）

**验收标准**：
- 所有 P0/P1 用例通过
- 首页加载 ≤ 2 秒
- 无明显阻塞性缺陷

---

### T12：部署脚本与本地运行配置

**目标**：实现一键本地启动和基础部署。

**输出**：
- `start.sh` / `start.bat` 一键启动脚本
- `requirements.txt` 与 `package.json` 依赖清单
- 环境变量模板 `.env.example`
- 数据库初始化脚本
- 使用说明文档
- 可选：docker-compose 配置

**验收标准**：
- 新环境按文档可 10 分钟内启动系统
- 后端、前端、数据库连接正常
- 邮件中心调用正常

---

## 五、风险与应对

| 风险 | 影响 | 应对措施 |
| :--- | :--- | :--- |
| Worktree 分支过多导致合并冲突 | 高 | 每 2-3 天同步一次 main，小步合并；优先合并基础框架 |
| 模块间数据口径不一致 | 中 | 统一状态字典、统一时间字段、统一关联方式 |
| 统一邮件中心接口变动 | 中 | 封装邮件中心客户端，接口变更只改一处 |
| Obsidian 目录读写冲突 | 中 | 文件操作加简单锁或时间戳校验，避免并发写同一文件 |
| 开发进度偏差 | 中 | 每个任务设置明确验收标准，每周检查进度 |
| 看板数据聚合性能差 | 中 | 关键指标预计算，使用索引，必要时加缓存 |

---

## 六、工具与规范

### 6.1 推荐工具

| 用途 | 工具 |
| :--- | :--- |
| 版本控制 | Git + Git Worktree |
| 后端框架 | FastAPI |
| 前端框架 | Vue 3 + Vite + Element Plus |
| 状态管理 | Pinia |
| 数据库 | MySQL + SQLAlchemy + Alembic |
| 接口文档 | FastAPI 自动 Swagger |
| 测试 | pytest + Vitest |
| 代码规范 | ruff + ESLint + Prettier |

### 6.2 代码规范

- 后端：PEP 8，使用 `ruff` 格式化
- 前端：ESLint + Prettier
- 分支命名：`feature-{模块名}`
- 提交信息：遵循 Conventional Commits
- API 路径：`/api/v1/{模块名}/{资源}`

### 6.3 提交规范示例

```
feat(operation): 新增运营问题录入接口
fix(meeting): 修复会议纪要参会人重复问题
docs(readme): 更新项目启动说明
refactor(common): 优化通用列表组件
```

---

## 七、里程碑与交付物

| 里程碑 | 时间 | 交付物 |
| :--- | :--- | :--- |
| M1 基础框架完成 | Week 1 末 | 可运行的前后端框架、数据库模型、通用组件 |
| M2 业务模块完成 | Week 3 末 | 运营监控、会议管理、知识库三个模块可用 |
| M3 收尾模块完成 | Week 4 末 | 首页看板、待办中心可用，系统完整闭环 |
| M4 系统可上线 | Week 5 末 | 通过集成测试，具备本地一键启动能力 |

---

## 八、附录

### 8.1 常用 Git Worktree 命令速查

```bash
# 查看所有 worktree
git worktree list

# 创建新 worktree
git worktree add <path> <branch>

# 移除 worktree（不删除分支）
git worktree remove <path>

# 清理已删除目录的 worktree 记录
git worktree prune

# 在 feature 分支同步 main 最新代码
git fetch origin
git rebase origin/main
```

### 8.2 版本历史

| 版本 | 日期 | 修改内容 | 作者 |
| :--- | :--- | :--- | :--- |
| v1.0 | 2026-07-13 | 初始开发计划，含 Worktree 并行开发方案 | 老大 |

---

**文档状态**：评审中  
**下次评审重点**：确认开发阶段划分、确认 Worktree 目录位置、确认各模块工期是否可行
