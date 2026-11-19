# 排版管理（PB 批次）共用契约 — 所有 AI 开发者必读

- 权威方案：`docs/排版管理模块设计方案_评审稿.md` **v1.2（2026-11-18 老大拍板）**；交互基准 `docs/排版管理_页面Demo.html` v1.2。
- 决策结论：①5 页 + 默认落地「排版跟踪」②倒排 −15/−8/−3/−1 ③CRM 提前 7 自然日才准入，**默认自动顺延、支持单据级手工例外放行** ④自动顺延直到成功上线（≥2 重点、≥3 异常、不自动发邮件）⑤督办邮件「唯一回执码 + 四字段」为主通道 ⑥团队×类型一键批量、24h 冷却 + 停滞 7 天 + 5 类例外 ⑦本期**不做**部分上线、**不接**任务中心、**不回写**运营 BUG 工单。

## 技术契约（禁自造第二份）
| 项 | 唯一落点 |
| :--- | :--- |
| 枚举 / 倒排偏移 / 例外原因闭集 | `backend/constants/paiban.py` |
| 表名前缀 | `pmwb_pb_*`；L1 建 `pmwb_pb_version_plan` / `pmwb_pb_version_change_log` |
| 模型 | `backend/db/models_paiban.py`（`models.py` 末尾一行导入收集进 `Base.metadata`） |
| API | `/api/v1/paiban/*`，单一 router `backend/routers/paiban.py`，逐子任务追加端点 |
| 包络 | `{code,message,data}`；前端 `request.js` 已解包，`api/paiban.js` **禁二次解包** |
| 服务层 | 每个子域一个 `backend/services/paiban_*.py`；**禁在 router 里写第二份 SQL / 口径公式** |
| 时间 | `now_cn()`（UTC+8 naive），禁 `utcnow()` |
| 状态 | 新域注册到 `constants/status_registry.py` + 前端 `/meta/status-domains` 两处 |
| 团队/系统 | 现网 `active_team_systems()` + 人员中台映射；禁 LIKE 硬凑 |
| 邮件 | 统一 `dispatch_email`；AI 自测一律 `dry_run`，真发仅老大页面显式 `confirm_send=true` |
| 前端 | 令牌只用 `styles/design.css` 变量，禁硬编码十六进制、禁 `:deep()`；新组件放 `views/paiban/` |

## 共树纪律（重要，覆盖旧「切子分支」约定）
- 本仓库**多 AI 共树**：按 2026-08-15 git 事故整改，**禁 `git checkout` 切分支 / 禁 worktree / 禁 `--all`**；沙箱切分支曾导致未提交文件丢失。
- 隔离方式 = **独立文件集 + 精确文件清单提交**：`~/.workbuddy/bin/git-safe-commit.sh`，`git commit -- <逐文件列出>`；`verify_*` 脚本需 `git add -f`。
- 当前 `main` 上已有其他任务的未提交改动，**只读、不碰、不带入本批次提交**。
- 改后端 `.py` 后主服务重启**一律由老大本人操作**；AI 只给「服务名 + 命令 + 验证方式」，或另起 8010 实例加载新代码做端到端验证。
- Alembic 存在多 head（坏壳 20260908105939），**执行必须显式 revision id**。

## 依赖链
`pb-1 / pb-2 → pb-3 → pb-4 / pb-5 / pb-6 → pb-9 → pb-7 → pb-8`
（pb-9 与 pb-5/pb-6 先约定接口可并行：反馈写主行状态、风险合并、回执状态三处契约）

## 子任务索引
| task-id | 对应方案 | 标题 | 状态 |
| :--- | :--- | :--- | :--- |
| pb-1 | L1 | 版本计划登记与回落 + 准入模式配置 | 🟡待审查（开发+自测完成） |
| pb-2 | L2 | 候选池与纳入 | ✅完成（Vicky2号） |
| pb-3 | L3 | 四环节状态机 + 准入判定 + 自动顺延 | ✅完成（Vicky2号） |
| pb-4 | L4 | 团队跟踪视图 | ✅完成（Vicky2号） |
| pb-5 | L5 | 风险事件 | ✅完成（Vicky2号） |
| pb-6 | L6 | 批量督办 + 回执锚点 | ✅完成（Vicky2号） |
| pb-7 | L9 | 反馈同步与便捷录入 | ✅完成（Vicky2号） |
| pb-8 | L7 | 版本概览与口径 | ✅完成（Vicky2号） |
| pb-9 | L8 | 回归与真实页面验证 | ✅完成（Vicky2号） |
