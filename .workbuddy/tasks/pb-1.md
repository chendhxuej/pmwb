# pb-1（L1）版本计划登记与回落 + 准入模式配置

- 级别：S1（方案已拍板）｜ blockedBy：无 ｜ 开发者：Vicky2号 ｜ 状态：🟡待审查（开发+自测完成）
- 交付：pytest 12 PASS / 迁移 SQLite 真跑 / vite build 通过 / 真实 Chrome DOM 16 PASS；脚本 `scripts/verify_paiban_l1_dom.mjs`。
- 方案章节：4.2 / 5.1 / 5.8 / 9-B1 / 10-AC-A

## 目标
让「哪天上版、四环节各在哪天截止、哪些系统有特殊准入规则」有唯一权威来源，且未单独配置的系统自动回落统一默认计划。

## 范围
- 建 `pmwb_pb_version_plan`（默认 + 系统覆盖）：版本标识、范围、类型、发布日、计划状态、准入模式、提前天数、是否允许临时合入、显式下一版、备注。
- 建 `pmwb_pb_version_change_log`：发布日 / 状态 / 准入规则变更留痕（字段、旧值、新值、影响在跟工单数、操作人、时间）。
- 唯一服务 `services/paiban_version.py`：`derive_deadlines()` 按 −15/−8/−3/−1 派生四环节截止 + 冻结日 + 准入判定时点（**派生不落库**，改期自动全量重算）；`resolve_plan(system)` 回落解析（**不落副本**，返回 source=专属/默认）；`next_plan()` 版本序列唯一解析。
- 路由：`GET /paiban/versions`（筛选/列表）、`GET /paiban/meta`（枚举 + 系统字典 + 偏移）、`GET /paiban/versions/{id}`（含派生截止与变更日志）、`POST /paiban/versions`、`PATCH /paiban/versions/{id}`、`GET /paiban/resolve?system=`（回落预览）。
- 前端：菜单插在「任务中心」与「需求与交付」之间；5 页签容器 + 默认「排版跟踪」占位；「版本计划」页完整（列表 / 登记编辑 / 派生截止实时预览 / 回落预览 / 变更日志）。

## 边界
- **不做**工单、状态机、准入判定、顺延、邮件；单据级手工例外放行属 pb-3，本任务只提供规则配置与变更留痕。
- 不读写需求 / 运营工单本体；不接任务中心；不改运行态其它模块。
- 倒排偏移、准入模式枚举只在 `constants/paiban.py` 定义一次，前端从 `/meta` 取，禁另写一份。

## 验收
- 回落可复算：无专属计划的系统 `resolve_plan` 必返回默认计划且 `source=default`；默认计划改期后回落结果的截止日/准入时点同步变化，DB 无副本。
- 同系统内版本标识唯一；`scope=system` 的系统名必须来自系统字典。
- 改发布日 / 状态 / 准入规则各写一条变更日志，字段与旧新值正确。
- CRM 计划配 `admit_mode=wait_release_n_days, admit_lead_days=7, allow_temp_merge=0`；此配置是全局唯一源，无工单级开关。
- `pytest backend/tests/test_paiban_version.py` 全绿；`npx vite build --outDir dist-paiban` 通过。
