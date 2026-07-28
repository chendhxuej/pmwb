# PMWB 多 AI 协同开发规范 v1.0

> 目标：支持 Vicky2号 + 其他 AI 工具分支化协同开发，Vicky2号担任集成者，确保主干质量。
>
> 制定日期：2026-07-28 | 制定者：Vicky2号 | 适用：PMWB 项目所有开发任务

---

## 一、角色定义

| 角色 | 由谁担任 | 职责 |
|------|----------|------|
| **集成者 (Integrator)** | Vicky2号 | 任务拆解与分配、分支创建、代码审查、合版、推送归档 |
| **开发者 (Developer)** | 其他 AI 工具 / Vicky2号本人 | 在指定 feature 分支上完成开发任务、自测、提交 PR |
| **决策者 (Owner)** | 老大 | 需求确认、方案审批、授权归档推送 |

## 二、分支策略

### 2.1 分支模型

```
main (受保护，禁止直接推送)
  ├── feature/<task-id>-<简述>    # 功能开发分支
  ├── fix/<task-id>-<简述>        # 修复分支
  └── release/<version>           # 发布分支（按需）
```

### 2.2 规则

1. **main 受保护**：任何改动必须通过 feature 分支 → 集成者审查合入，禁止直接在 main 上开发或提交。
2. **分支命名**：`feature/<task-id>-<kebab-case-desc>`，如 `feature/mc-2-backend-proxy`。
3. **分支生命周期**：任务完成并合入 main 后，删除 feature 分支。
4. **分支基础**：新分支必须从最新 main 切出（`git checkout main && git pull && git checkout -b feature/...`）。

### 2.3 任务编号规则

- 格式：`<模块前缀>-<序号>`，如 `mc-1`（mail-center 第1个任务）、`tc-3`（task-center 第3个任务）。
- 序号由集成者分配，全局递增，不复用。

## 三、任务定义格式（Task Spec）

集成者为每个开发任务输出一份 Task Spec，格式如下：

```markdown
# Task: <task-id> - <任务标题>

## 基本信息
- **分支**: feature/<task-id>-<简述>
- **级别**: S1/S2/S3
- **预估**: <文件数/复杂度>
- **依赖**: <前置 task-id 或 无>

## 目标
<一段话描述这个任务要完成什么>

## 改动范围
| 类型 | 文件路径 | 说明 |
|------|----------|------|
| 新增 | backend/xxx.py | ... |
| 修改 | frontend/xxx.vue | ... |

## 技术要求
<列出关键技术约束、API 格式、数据模型等>

## 完成标准 (DoD)
- [ ] 代码实现完整
- [ ] 自测通过（列出具体验证项）
- [ ] 无调试代码残留
- [ ] commit message 符合规范

## 提交方式
1. 在指定分支上开发
2. 自测通过后 commit
3. 通知集成者审查
```

## 四、标准化任务认领与交付机制

> **核心原则**：所有 AI 工具之间**不共享会话上下文**，一切协调通过**项目文件系统**完成。TASKS.md 是唯一的协调界面。

### 4.1 开发者首次接入

```
打开项目后，按以下顺序读文件：
1. docs/COLLABORATIVE_DEV_WORKFLOW.md  ← 本文（协同流程）
2. .workbuddy/tasks/TASKS.md            ← 任务总表（找活干）
3. .workbuddy/memory/MEMORY.md          ← 项目约定（避坑）
4. docs/DEV_WORKFLOW.md                 ← 开发级别规范
```

### 4.2 任务认领流程（开发者操作）

```
1. 打开 .workbuddy/tasks/TASKS.md
2. 找到状态为「⬜待分配」且无依赖阻塞的任务
3. 将自己的名字写入该任务的「开发者」列
4. 将状态改为「🔵开发中」
5. 保存 TASKS.md
6. 读取 .workbuddy/tasks/<task-id>.md 获取详细 Spec
7. 切到 Task Spec 中指定的分支，开始开发
```

**认领规则**：
- 一次只认领一个任务（防止冲突）
- 先认领无依赖的、序号最小的任务
- 认领后在 TASKS.md 写清楚自己的名字（如 `Claude`、`Gemini`、`Vicky2号`）

### 4.3 任务交付流程（开发者操作）

```
1. 完成开发 + 自测（按 Task Spec 的 DoD 逐项验证）
2. commit（遵循第五节提交规范）
3. 编辑 .workbuddy/tasks/TASKS.md：
   - 状态改为「🟡待审查」
   - 在备注列写：交付时间 + 提交 SHA + 自测结果简述
   - 如有需要集成者注意的点，在备注中注明
4. 保存 TASKS.md
5. 任务交付完成——集成者（Vicky2号）下次检查时会自动发现并审查
```

**交付信号**：集成者通过检查 TASKS.md 中是否有 🟡待审查 行来发现交付，无需消息通知。

### 4.4 集成者发起任务

```
1. 集成者评估需求，拆解为独立任务
2. 分配 task-id（全局递增）
3. 从 main 切出 feature/<task-id>-<desc> 分支
4. 将分支推送到 origin
5. 编写 Task Spec → .workbuddy/tasks/<task-id>.md
6. 在 TASKS.md 新增一行，状态设为「⬜待分配」
```

### 4.5 集成者审查轮巡

```
每次会话开始，集成者必须：
1. 读取 .workbuddy/tasks/TASKS.md
2. 检查是否有「🟡待审查」状态的任务
3. 按 task-id 序号依次审查
```

**审查步骤**：
```
1. 切换审查视角读取代码改动：
   - git checkout feature/<task-id>-<desc>
   - git diff main...feature/<task-id>-<desc>
2. 逐项审查：
   - 功能完整性（对照 DoD）
   - 代码质量（无调试代码、无硬编码、异常处理）
   - 影响面（Grep 关联点、回归风险）
   - 约定一致性（API 路径、响应解包、端口、时区等）
3. 运行质量门禁全项（见第六节）
4. 审查结论：
   - ✅ 通过 → 合入 main，更新 TASKS.md 为「✅已合入」，删除 feature 分支
   - 🔴 不通过 → 更新 TASKS.md 为「🔴审查退回」，在备注列写明问题
```

### 4.6 审查退回后修复

```
1. 开发者发现任务状态变为「🔴审查退回」
2. 阅读备注列的问题描述
3. 在同一分支上修复问题
4. 重新提交，状态改为「🟡待审查」
```

### 4.7 归档与推送

```
1. 集成者在完成一批任务后，统一或按需推送 main 到 origin
2. 推送前检查：无密钥/临时文件误入
3. 推送后通知老大
4. 更新项目 memory
```

> **注意**：日常只提醒不自动推；老大说"归档"才自动推。

## 五、提交规范

### 5.1 Commit Message 格式

```
<type>(<scope>): <简述>

<可选正文，说明改了什么、为什么改>
```

**type 枚举**：
- `feat` — 新功能
- `fix` — 修复
- `refactor` — 重构
- `docs` — 文档
- `chore` — 杂项
- `test` — 测试
- `style` — 格式调整

**scope 示例**：`mail-center`, `task-center`, `knowledge`, `backend`, `frontend`

**示例**：
```
feat(mail-center): 后端代理层 - MailCenterProxyClient + 全量 CRUD 路由

新增 MailCenterProxyClient 通用代理类，支持 API Key 注入；
新增账号/通讯录/分组/模板/日志/发送的完整 CRUD 路由转发。
```

### 5.2 规则
- 一个 commit 对应一个明确的改动单元
- 不混合无关改动
- 不自动 push（除非老大说"归档"）

## 六、质量门禁

集成者合版前必须过：

| 检查项 | 方法 |
|--------|------|
| 后端测试 | `pytest` 全绿 |
| 前端测试 | `vitest run` 全绿 |
| 前端构建 | `npm run build` 无报错 |
| 浏览器冒烟 | 无头浏览器访问关键页面无白屏/报错 |
| 代码审查 | 无调试残留、无密钥、约定一致 |
| 影响面 | Grep 确认关联点覆盖 |

## 七、冲突处理

1. **分支冲突**：开发者负责 rebase 到最新 main 解决冲突，不直接 merge main 到 feature。
2. **设计分歧**：开发者不得私自改方案，反馈给集成者决策。
3. **依赖阻塞**：如果任务依赖的前置任务未完成，通知集成者协调。

## 八、文件归属

| 目录/文件 | 管理者 | 说明 |
|-----------|--------|------|
| `.workbuddy/tasks/` | 集成者 | Task Spec 存放 |
| `.workbuddy/memory/` | 集成者 | 项目记忆 |
| `docs/` | 集成者 | 项目文档 |
| `backend/` | 开发者+集成者 | 按任务分配 |
| `frontend/` | 开发者+集成者 | 按任务分配 |
| `scripts/` | 集成者 | 启动/运维脚本 |

## 九、任务追踪机制

### 9.1 任务看板

集成者在 `.workbuddy/tasks/` 目录维护任务状态：

```
.workbuddy/tasks/
  ├── TASKS.md              # 任务总表（所有任务状态一览）
  ├── mc-1-backend-proxy.md # 各任务 Spec 文件
  ├── mc-2-frontend-route.md
  └── ...
```

`TASKS.md` 格式：

| task-id | 标题 | 分支 | 级别 | 状态 | 开发者 | 备注 |
|---------|------|------|------|------|--------|------|
| mc-1 | 后端代理层 | feature/mc-1-backend-proxy | S2 | ✅已合入 | Vicky2号 | |
| mc-2 | 前端路由框架 | feature/mc-2-frontend-route | S2 | 🔵开发中 | Claude | |
| mc-3 | 发送日志页 | feature/mc-3-logs-view | S2 | ⬜待分配 | — | 依赖 mc-2 |

**状态枚举**：⬜待分配 → 🔵开发中 → 🟡待审查 → 🔴审查退回 → ✅已合入 / ❌已取消

### 9.2 跨 AI 交接要点

其他 AI 工具**不共享会话上下文**，Task Spec 必须自包含：

1. **背景上下文**：项目技术栈、相关文件路径、已有约定（指向 DEV_WORKFLOW.md、MEMORY.md）
2. **精确改动范围**：每个要改的文件路径 + 具体改什么，不留模糊空间
3. **验收标准可执行**：给出具体的验证命令（如 `pytest xxx`、`curl xxx`），不写"确保正常"
4. **禁止项清单**：列出不能动的文件、不能违反的约定（如 API 解包规则、时区处理）
5. **起点指引**：分支名、从哪个 commit 切出、开发环境路径

## 十、与现有 DEV_WORKFLOW.md 的关系

本规范在 `DEV_WORKFLOW.md` v1.0 的基础上增加多 AI 协同分支化开发流程：
- **DEV_WORKFLOW.md** 定义开发任务的执行级别和步骤（S1-S4），仍然有效。
- **本规范** 定义多人/多 AI 协同时的分支、任务分配、审查合版机制。
- 两者叠加使用：开发者按 DEV_WORKFLOW 步骤执行，集成者按本规范管理分支和合版。

---

_v1.0 — 2026-07-28 — Vicky2号_
