# PMWB 开发任务总表

> 集成者：Vicky2号 | 更新时间：2026-08-09
>
> **AI 开发者请先看**：`docs/COLLABORATIVE_DEV_WORKFLOW.md` 第四节「标准化任务认领与交付机制」

---

## 快速认领指南（给其他 AI 工具）

```
1. 找 ⬜待分配 且无依赖阻塞的最小编号任务
2. 把「开发者」列改成你的名字，「状态」改为 🔵开发中
3. 读 .workbuddy/tasks/<task-id>.md 获取完整开发 Spec
4. 切到指定分支开始干活
5. 完成后状态改 🟡待审查，备注写交付说明
```

---

## 批次一：邮件中心整合（Mail Center Integration）— ✅已完成

| task-id | 标题 | 分支 | 级别 | 状态 | 开发者 | 备注 |
|---------|------|------|------|------|--------|------|
| mc-1 | 后端代理层：配置+ProxyClient+路由 | feature/mc-1-backend-proxy | S2 | ✅已合入 | Vicky2号 | 25条路由，合并日志端点 |
| mc-2 | 前端路由与菜单：/mail-center 路由组 | feature/mc-2-frontend-route | S2 | ✅已合入 | 晓伴→Vicky2号审查 | 审查剔除3个P0无关文件后合入 |
| mc-3 | 发送日志页（合并展示） | feature/mc-3-logs-view | S2 | ✅已合入 | 晓伴→Vicky2号审查 | 812c8bc，审查移除未使用 mcError ref |
| mc-4 | 账号管理+通讯录/分组+模板管理 | feature/mc-4-admin-pages | S2 | ✅已合入 | 晓伴→Vicky2号审查 | 1cb76d3，4页CRUD完整 |
| mc-5 | 测试验证+浏览器冒烟+归档 | feature/mc-5-verify | S3 | ✅已合入 | 晓伴 | pytest 43/44, vitest 4/4, build ok |

---

## 批次二：邮件中心优化（Mail Center Optimization）

> 依赖：批次一 mc-1~5 全部 ✅已合入
> 原则：只做 PMWB 侧增值功能（统一邮件中心不具备的能力），不替邮件中心重建已有页面/功能

| task-id | 标题 | 分支 | 级别 | 状态 | 开发者 | 备注 |
|---------|------|------|------|------|--------|------|
| mc-opt-1 | 邮件统计概览卡片 | feature/mc-opt-1-stats | S2 | ✅已合入 | 晓伴→Vicky2号审查 | 7d2014d 合入，见 reviews/mc-opt-1-R1.md |

---

## 批次三：首页看板重构（Dashboard Rebuild）

> 依赖：无（可与批次二并行开发）
> 目标：参考「数智化部 AI 工作台」截图风格，丰富图表，提升信息阅读效率
> ⚠️ **方案已于 2026-08-03 被老大指令覆盖**：原「新旧共存 + /dashboard-v2」策略作废，`DashboardV2View.vue` 与 `/dashboard-v2` 路由已删除（08-04 随 be5c653 清理完毕）。
> ✅ 现状：**旧版 `HomeView.vue` 是唯一看板页**，db-1(ECharts 组件)/db-2(后端接口) 成果保留并服务此页；db-3/4/5 的 KPI/图表/模块卡已直接落在 HomeView。

| task-id | 标题 | 分支 | 级别 | 状态 | 开发者 | 备注 |
|---------|------|------|------|------|--------|------|
| db-1 | 引入 ECharts + 封装图表组件 | feature/db-1-echarts | S2 | ✅已合入 | 晓伴→Vicky2号审查 | 0b6bbc0 合入，见 reviews/db-1-R1.md |
| db-2 | 后端 Dashboard 统计接口扩展 | feature/db-2-api | S2 | ✅已合入 | 晓伴→Vicky2号审查 | f6b9406 合入，见 reviews/db-2-R1.md |
| db-3 | 首页 KPI 统计区重构（大数字卡片） | feature/db-3-kpi | S2 | ✅已合入 | Vicky2号 | 退回后由 DashboardV2View(/dashboard-v2) 统一承载 KPI 卡片，见 a810718 |
| db-4 | 首页图表区扩展（柱/线/饼/进度条） | feature/db-4-charts | S2 | ✅已合入 | Vicky2号 | 退回后由 DashboardV2View 统一承载趋势/分布/进度图表，见 a810718 |
| db-5 | 各模块数据可视化卡片 | feature/db-5-modules | S2 | ✅已合入 | Vicky2号 | 退回后由 DashboardV2View 统一承载 6 模块统计卡，见 a810718 |

---

## 批次四：任务中心"编辑"深链（需求1）

> 依赖：无 | 目标：任务中心每类工单操作列新增"编辑"，带 source_id 深链跳来源模块并定位/编辑该工单

| task-id | 标题 | 分支 | 级别 | 状态 | 开发者 | 备注 |
|---------|------|------|------|------|--------|------|
| tc-1 | 后端：6类采集器 source_url 改为深链(含 source_id)，修正待办路由 | feature/tc-1-source-url-deeplink | S2 | ✅已合入 | 晓伴→Vicky2号审查 | 52f7616，与ma-1冲突后合并13 pytest 通过，见 reviews/tc-1-R1.md |
| tc-2 | 前端：任务中心操作列新增编辑按钮，gotoSource 深链跳转 | feature/tc-2-edit-button | S2 | ✅已合入 | 晓伴→Vicky2号审查 | ab78b07，frontend build 通过，见 reviews/tc-2-R1.md |
| tc-3 | 前端：5来源模块支持 ?id= 深链定位并进入编辑态 | feature/tc-3-module-deeplink | S2 | ✅已合入 | 晓伴→Vicky2号审查 | ab78b07，分支曾被force push为空，已恢复3e0288c并合并，frontend build 通过，见 reviews/tc-3-R3.md |

---

## 批次五：会议行动项可见性修复（需求2）

> 依赖：无 | 目标：会议行动项标签展示全部行动项，已同步的标"已转待办"徽标

| task-id | 标题 | 分支 | 级别 | 状态 | 开发者 | 备注 |
|---------|------|------|------|------|--------|------|
| ma-1 | 后端：会议行动项完整返回 + synced_to_todo 标记 | feature/ma-1-meeting-action-visible | S2 | ✅已合入 | 晓伴→Vicky2号审查 | 4fabcf3 已入主干，5 pytest 通过，已随 tc-1 合并保留 |
| ma-2 | 前端：会议行动项"已转待办"徽标 | feature/ma-2-synced-badge | S2 | ✅已合入 | 晓伴→Vicky2号审查 | ea5f069 已入主干，build 通过 |

---

## 批次六：统一邮件中心联系人复用人员中台（需求3，跨仓库）

> 依赖：人员中台(8001)运行并暴露 staff 列表接口 | 仓库：D:\项目\统一邮件中心\server（独立 git） | 目标：联系人只读复用中台，禁用本地增改删
> ⚠️ 该仓库当前有较多未提交改动（疑似他人在开发），开工前需先 `git stash`/`commit` 自身基线，再切到下列分支。

| task-id | 标题 | 分支(邮件中心仓库) | 级别 | 状态 | 开发者 | 备注 |
|---------|------|------|------|------|--------|------|
| umc-1 | 邮件中心：新增人员中台出站客户端 masterService.ts | feature/umc-1-master-service | S2 | ✅已合入 | 晓伴→Vicky2号审查 | 590b7bb（tongyi_email 仓库），11 测试通过，tsc 无类型错误，见 reviews/umc-1-R1.md |
| umc-2 | 邮件中心：contacts 读路径改中台 + 禁用本地增改删 | feature/umc-2-contacts-from-master | S2 | ✅已合入 | 晓伴→Vicky2号审查 | 40a2690（tongyi_email 仓库），R1 P1-1/P2-1 已修复，tsc 通过，见 reviews/umc-2-R2.md |
| umc-3 | 邮件中心前端：通讯录只读展示 | feature/umc-3-contacts-readonly | S2 | ✅已合入 | 晓伴→Vicky2号审查 | 83cac81（tongyi_email 仓库），只读展示无编辑入口，tsc 通过，见 reviews/umc-3-R1.md |

---

## 批次七：督办邮件服务（sup-2）

> 目标：提供统一督办邮件出站口，支持工单/运营问题/开发工单/需求/会议行动项一键发送督办邮件
> ⚠️ 原提交 `59c4e8f` 引入 `routers/supervise.py` 错误导入 `operation_service`，导致后端启动即崩、看门狗循环重启；已在 `3594720` 修复

| task-id | 标题 | 分支 | 级别 | 状态 | 开发者 | 备注 |
|---------|------|------|------|------|--------|------|
| sup-2 | 新增督办邮件服务 + 修复导入崩溃 | feature/sup-2-supervise-service | S4 | ✅已合入 | 晓伴→Vicky2号审查 | 5801eca，新增 POST /api/v1/supervise/ticket 和 /action；pytest 13 passed，导入链干净 |

---

## 批次八：会议日程-行动项子模块（ma-3/ma-4/ma-5）

> 依赖：批次七 sup-2（督办邮件服务）✅已合入 | 目标：在「会议日程」模块下增加「行动项」子页面，支持跨会议查询、筛选、状态切换、一键督办

| task-id | 标题 | 分支 | 级别 | 状态 | 开发者 | 备注 |
|---------|------|------|------|------|--------|------|
| ma-3 | 后端：会议行动项查询/状态更新/督办接口 | feature/ma-3-action-backend | S2 | ✅已合入 | Vicky2号 | fcb17cd，pytest 9 passed，修复 dashboard 缺失导入 |
| ma-4 | 前端：会议行动项子页面 + 菜单 | feature/ma-4-action-frontend | S2 | ✅已合入 | Vicky2号 | 00d9005，vite build passed |
| ma-5 | 前后端：会议行动项支持完整编辑 | feature/ma-5-action-edit | S2 | ✅已合入 | Vicky2号 | 238b957，pytest 12 passed，vite build passed |

---

## 批次九：孤儿分支成果同步与看板收敛（2026-08-01 ~ 08-04）

> 背景：08-01 之后有 7 个 feature 分支在**沙箱残缺副本仓库**中创建并推送，git 历史与 `origin/main` 断裂（孤儿分支，
> `git diff origin/main` 显示删除数万行），无法安全 merge——直接合入会把 main 的代码当"删除"合并掉。
> 处置：改为**以完整工作目录为准**，基于 `origin/main` 重建索引后一次性同步真实成果，孤儿分支冻结不合。

| task-id | 标题 | 分支 | 级别 | 状态 | 开发者 | 备注 |
|---------|------|------|------|------|--------|------|
| sync-1 | 工作目录成果同步入主干（50 文件） | feature/sync-0804-main | S2 | ✅已合入 | Vicky2号 | be5c653 fast-forward 到 main；含首页看板收敛、会议议题背景、工单反馈附件、邮件模板化等 |
| sync-2 | 修复 dashboard 跨方言统计回归 | （随 sync-1） | S3 | ✅已合入 | Vicky2号 | `cast(start_time, Date)` 在 SQLite 走 numeric affinity 失效 → 改 naive datetime 区间；pytest 116 passed |
| sync-3 | 移植 ui-2 抽屉草稿持久化 | （随 sync-1 后续） | S2 | ✅已合入 | Vicky2号 | 重写 `useDrawerDraft.js`（原分支版 `startWatching()` 从未调用、storageKey 无记录 ID、误用 `formRef.value` 处理 reactive），接入 WorkOrderView 录入弹窗 |

**冻结不合的孤儿分支**（功能已随 sync-1 进入 main，分支仅留档）：
`feature/db-6-dashboard-v2`（改的是已废弃的 DashboardV2View）、`feature/mc-6-email-personnel`、
`feature/meeting-agenda-optimize`、`feature/meeting-agenda-background`、`feature/operation-feedback-attachments`、
`feature/ui-2-drawer-draft`、`feature/ui-3-dashboard-polish`。

⚠️ **防复发**：沙箱环境下的 `.git` 常是残缺副本（当前分支仅跟踪 60 文件，`origin/main` 有 327 个）。
在沙箱内新建分支前必须先确认 `git merge-base origin/main HEAD` 有输出；无输出即孤儿分支，成果需改走"工作目录 + read-tree 重建索引"方式同步。

---

## 批次十：AI总结模块（WorkReport，wr-1/2/3）

> 开发于 2026-08-05 ~ 08-07 | 目标：自动生成日报/周报/月报/自定义报告（LLM 润色，不可用时规则模板兜底）；支持生成/查看/编辑/删除/定稿/邮件发送；定稿自动归档 Obsidian `15-工作总结/{类型}/{日期}.md`。
> 接线点：后端 `backend/routers/work_report.py`（前缀 `/api/v1/work-reports`，注册 `main.py`）；模型 `PmwbWorkReport`（`pmwb_work_report` 含 `cc TEXT` 列）；前端路由 `work-report`（菜单「AI总结」，`WorkReportView.vue`）。
> ⚠️ 现状：三批次均已合入 main（152576b / b21e913 / 3ecc47e）；曾因沙箱对象库损坏一度「仅存磁盘未入库」，已在 sync-1 批次一并抢救入主干，无需回退。

| task-id | 标题 | 分支 | 级别 | 状态 | 开发者 | 备注 |
|---------|------|------|------|------|--------|------|
| wr-1 | AI总结(WorkReport)模块：日报/周报/月报生成+定稿归档Obsidian+删除修复 | feature/wr-1-work-report-module | S1 | ✅已合入 | 晓伴→Vicky2号审查 | 152576b，含 LLM 润色降级规则模板 |
| wr-2 | AI总结优化：日报/周报/月报结构+左侧分类栏修复 | feature/wr-2-summary-optimize | S2 | ✅已合入 | 晓伴→Vicky2号审查 | b21e913 |
| wr-3 | AI总结报告内容强化：上线需求逐条总结+页面交互恢复+集成者管控 | feature/wr-3-report-content | S2 | ✅已合入 | 晓伴→Vicky2号审查 | 3ecc47e |

---

## 批次十一：工单模块督办按钮（sup-3，前端）

> 依赖：批次七 sup-2（督办邮件服务）✅已合入 | 目标：开发工单/运营问题/需求等工单类模块列表与详情新增"邮件督办"按钮，弹窗选场景+收件人+留言，调 sup-2 发送

| task-id | 标题 | 分支 | 级别 | 状态 | 开发者 | 备注 |
|---------|------|------|------|------|--------|------|
| sup-3 | 各工单模块督办按钮（前端） | sup-3-clean | S2 | ✅已合入 | 晓伴→Vicky2号审查 | 491ec82 合入 main；⚠️ 已删除污染分支 `feature/sup-3-supervise-dialog`(6c0b046)，其会回退本批次+wr-2/3 成果，切勿合入 |

---

## 批次十二：业务知识中心重构（kc-2，多对多关联 + 主笔记体系）

> 设计依据：`C:\Users\chend\.workbuddy\plans\electric-vortex-lovelace.md`（方案 v2.0，已与老大对齐关键决策）
> 核心目标：以 Obsidian 原生能力把「业务对象」作为知识中心——每个二级领域一个业务知识主笔记（All-in-one），过程性内容（需求/工单/会议/运营）独立成文件并通过 `[[链接]]` + `pmwb_knowledge_link` 关联表与主笔记双向打通。
> 关键决策：①主笔记粒度=二级领域；②过程性内容独立成文件；③需求"已关闭"语义改"已上线"并触发操作手册归档；④运营工单新增 4 结构化字段。
> 依赖关系：批次 1（kc-2-1）为基础设施，已合入 ✅；批次 2~6 可并行；批次 7（kc-2-7）终验主笔记体系。

| task-id | 标题 | 分支 | 级别 | 状态 | 开发者 | 备注 |
|---------|------|------|------|------|--------|------|
| kc-2-1 | 知识关联数据模型与基础设施（关联表+4字段+服务+前端KnowledgeLinker雏形） | feature/kc-2-1-knowledge-link-model | S2 | ✅已合入 | 晓伴→Vicky2号审查 | 9e597eb 合入；含 knowledge_link_service + FK 迁移 |
| kc-2-2 | 业务知识主笔记 + 按领域浏览重构（前端树形） | feature/kc-2-2-domain-main-note | S2 | ✅已合入 | Vicky2号 | 与 kc-2-7 合并实现；note_type 列+迁移(20260809000002)+ensure自动保活+子笔记摘要聚合+DomainKnowledgeView 树形 |
| kc-2-3 | 需求沉淀 + 用户故事规则沉淀 + 操作手册归档 | feature/kc-2-3-requirement-sediment | S2 | ✅已合入 | Vicky2号 | 8bc88ff 合入；sediment_requirement 回链主笔记 + sediment_requirement_rules(场景规则子笔记幂等替换) + archive_requirement_manual(交付物归档)；前端 KnowledgeLinker 接入+已关闭→已上线文案 |
| kc-2-4 | 运营工单结构化 + 多选关联沉淀 | feature/kc-2-4-operation-knowledge | S2 | ✅已合入 | Vicky2号 | 14b03a4 合入；sediment_operation_rules(场景规则子笔记幂等替换+中文枚举标签)+domain_code 必填+4 结构化下拉；WorkOrderView/OperationView 接入 |
| kc-2-5 | 会议中心：纪要覆盖/删除/多选关联 | feature/kc-2-5-meeting-sediment | S2 | ✅已合入 | Vicky2号 | 6a88b14 合入；MeetingView 业务领域必填+force 覆盖/删除纪要锁定测试(test_obsidian_link 6 passed)；后端 force/delete 能力前序 kc-2-1 已具备 |
| kc-2-6 | 回归验证 + 文档 + 存量迁移脚本 | feature/kc-2-6-clean | S3 | ✅已合入 | Vicky2号 | b15df23 合入（抢救资产）；⚠️ 已删除污染分支 `feature/kc-2-6-validation-migration`(e407acb)，其会回退 kc-2-1/sup-3/wr 成果，切勿合入 |
| kc-2-7 | 业务知识主笔记体系（Domain Main Note）补全 | feature/kc-2-7-domain-main-note | S2 | ✅已随 kc-2-2 合并实现 | Vicky2号 | 方案门禁已确认（系统自动保活/自动汇总子笔记摘要/树形），功能并入 kc-2-2 一并合入；分支 feature/kc-2-7-* 不再独立建 |

---

## 批次十三：Obsidian 业务知识结构优化（kc-3）

> 背景：老大评估现有业务知识沉淀/关联逻辑"乱、不够清晰集中"。2026-08-09 经方案对齐批准后执行。
> 核心目标：①全面领域化（运营/会议/开发交付归入 `01-业务知识/{领域}/` 树）；②需求沉淀笔记同置到需求自身文件夹；③领域浏览聚合口径统一（源表+链接并集）。
> 设计依据：`C:\Users\chend\.workbuddy\plans\quantum-aurora-einstein.md`（P0~P5 分阶段）。

| task-id | 标题 | 分支 | 级别 | 状态 | 开发者 | 备注 |
|---------|------|------|------|------|--------|------|
| kc-3-1 | 需求 domain_code 端到端贯通（修规则沉淀404） | feature/kc-3-1-requirement-domain-code | S2 | ✅已合入 | Vicky2号 | 32cfd62；`requirement._merge_ext` 补 `domain_code` + 前端必填/回显，根因是 API 漏返字段致库空 |
| kc-3-2 | 需求知识笔记同置到需求自身文件夹 | feature/kc-3-2-requirement-sediment-colocated | S2 | ✅已合入 | Vicky2号 | 4b10f47；废弃 `10-业务建设/需求沉淀`，`sediment_requirement` 改写需求文件夹；迁移脚本移动 2 条真实笔记 |
| kc-3-3 | 领域浏览聚合改为源表+链接并集 + 源记录 domain_code 回填 | feature/kc-3-3-domain-browse-aggregation | S2 | ✅已合入 | Vicky2号 | c94af0e；消除"时间线有、需求/运营空"错位；`link_note` 建关联时回填源记录 domain_code；新增回归测试 6 passed + 存量回填脚本（已对真实库回填 2 条） |
| kc-3-4 | 路径权威源（obsidian_paths.resolve_domain_path） | feature/kc-3-4-domain-tree-routing | S2 | ✅已合入 | Vicky2号 | cbfe3d0；新增 `backend/services/obsidian_paths.py` 统一领域树路径，取代散落硬编码 |
| kc-3-5 | 运营/会议/开发交付归入 `01-业务知识/{领域}/` 树 | feature/kc-3-4-domain-tree-routing | S2 | ✅已合入 | Vicky2号 | cbfe3d0（与 kc-3-4 同分支合并）；sediment_operation/meeting/dev_ticket 经路径权威源落 `运营/会议/开发交付/` 子目录；domain_code 缺失时安全回退旧路径；迁移脚本已对真实库执行（1 条会议迁入订单中心/会议/，13 条无 domain_code 跳过） |

---

## 批次十四：知识中心体系化重构（以业务为中心，knowledge hub）

> 设计依据：`docs/kc3_knowledge_hub_plan.md`（S1 方案，2026-08-11 老大确认落地）
> 核心目标：以 Obsidian 业务知识笔记为底座，建立「过程模块 → 沉淀引擎 + 关联登记表 → 主笔记自动回流 → 业务时间线」闭环；知识中心 UI 收敛为 3 个以业务为中心的视图（全景 HUB / 检索 / 沉淀向导）。
> 关键决策（已确认）：①开发工单子模块取消，退出知识沉淀链路（数据保留）；②SQL脚本库补齐 `domain_code` 后保留；③主笔记回写按「业务事实保守分级」策略（§2/§3 仅已关闭+变更标记需求回写，其余放开）。
> 依赖：kc-2 / kc-3 骨架已合入 ✅；本批次在主干之上开发。
> ⚠️ **并行模式（2026-08-11 确认开放）**：允许多 AI 并行认领。各任务走独立子分支 `feature/kc4-N-<desc>`，开发完 PR 合入父分支 `feature/kc4-knowledge-hub`；**仅 Vicky2号（集成者）可 commit/push/merge 主干**，其他 AI 在子分支开发后走 `.workbuddy/reviews/` 异步评审。认领：改「开发者」列 + 状态🔵开发中，读 `.workbuddy/tasks/kc4-N.md` 拿 Spec。会话结束须在 `D:/项目/_<branch>_backup/` 备份未提交内容（防沙箱切分支丢文件）。

| task-id | 标题 | 分支 | 级别 | 状态 | 开发者 | 备注 |
|---------|------|------|------|------|--------|------|
| kc4-1 | 关联表扩展 link：event_type/event_date/summary + 存量回填 | feature/kc4-1-2-main-note-autoflow | S2 | ✅已合版 | Vicky2号 | 迁移 20260812000001；12 条存量已回填；已合入 main f9e8101 |
| kc4-2 | 主笔记自动回流引擎 sync_main_note_from_links（分级回写 + 自动触发） | feature/kc4-1-2-main-note-autoflow | S2 | ✅已合版 | Vicky2号 | AUTO 标记块保人工区零覆盖；迁移 20260812000002；单测 8 例全过；已合入 main f9e8101 |
| kc4-3 | 业务时间线接口 business_timeline + 前端时间线组件 | feature/kc4-3-timeline | S2 | ✅已合版 | Vicky2号 | GET /business-timeline 端点 + BusinessTimeline.vue 时间轴组件; 单测 6 例; 冒烟 PASS(9事件+筛选); 已合入 main b2ce43e |
| kc4-4 | 需求交付物去开发工单（直挂文件 + archive 改造 + 新端点） | feature/kc4-4-delivery | S2 | ✅已合版 | Vicky2号 | deliverables JSON 字段 + 归档改造(新旧链路兼容) + CRUD 端点; 单测 6 例; 已合入 main 57753fa |
| kc4-5 | SQL脚本库补 domain_code（迁移 + CRUD + 检索纳入） | feature/kc4-5-sql-domain | S2 | ✅已合版 | 其他AI(并行) | 后端模型/迁移/路由/Schema + 前端视图/领域选择器/过滤; 已全部就位 |
| kc4-6 | 知识中心 UI 三视图重构（HUB/检索/沉淀向导）+ 产品圣经去硬编码 | feature/kc4-6-ui-views | S2 | ✅已完成 | Vicky2号 | 3 视图+产品圣经去硬编码;构建+冒烟 PASS |

---

## ⚠️ 已删除的危险分支（2026-08-09 清理，永久勿合）

以下两个分支曾存在于 origin，实为**孤儿污染分支**（在沙箱残缺副本仓库创建，`git diff origin/main` 显示删除数万行），合入会把 main 成果当"删除"合并掉：

| 已删分支 | 提交 | 危害 | 现状 |
|----------|------|------|------|
| `feature/sup-3-supervise-dialog` | 6c0b046 | 回退 sup-3 + wr-2 + wr-3 全部成果 | 已从 origin + 本地远端跟踪引用删除 |
| `feature/kc-2-6-validation-migration` | e407acb | 回退 kc-2-1 + sup-3 + wr 全部成果 | 已从 origin + 本地远端跟踪引用删除 |

> 兜底：若 `git branch -r` 又出现这两个分支，立即 `git push origin --delete` + 清 `.git/refs/remotes/origin/feature/` 下对应 `.lock` 与引用文件（沙箱 safe-delete 拦截 `rm`，用 ctypes `kernel32.DeleteFileW` 删）。

---

## 状态枚举
⬜待分配 → 🔵开发中 → 🟡待审查 → 🔴审查退回 → ✅已合入 / ❌已取消

## 任务 Spec 文件
存放于同目录 `.workbuddy/tasks/<task-id>.md`，每个任务一份，自包含全部开发上下文。
