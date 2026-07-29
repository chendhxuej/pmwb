# PMWB 开发任务总表

> 集成者：Vicky2号 | 更新时间：2026-07-29
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
> ⚠️ 新旧共存策略：新页面走 /dashboard-v2 路由，旧 HomeView（/）不动；老大确认 OK 后再替换 / 指向新页面
> ✅ 新版看板已落地：`DashboardV2View.vue` @ `/dashboard-v2`（侧栏"新版看板"），旧首页保留。db-3/4/5 退回项已由该页面统一承载（KPI/图表/模块卡）。

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
| tc-1 | 后端：6类采集器 source_url 改为深链(含 source_id)，修正待办路由 | feature/tc-1-source-url-deeplink | S2 | 🟡待审查 | 晓伴 | 89ecb1d，8 pytest 通过 |
| tc-2 | 前端：任务中心操作列新增编辑按钮，gotoSource 深链跳转 | feature/tc-2-edit-button | S2 | 🟡待审查 | 晓伴 | build+vitest 通过 |
| tc-3 | 前端：5来源模块支持 ?id= 深链定位并进入编辑态 | feature/tc-3-module-deeplink | S2 | 🟡待审查 | 晓伴 | 78df319，含后端 by-child 端点 |

---

## 批次五：会议行动项可见性修复（需求2）

> 依赖：无 | 目标：会议行动项标签展示全部行动项，已同步的标"已转待办"徽标

| task-id | 标题 | 分支 | 级别 | 状态 | 开发者 | 备注 |
|---------|------|------|------|------|--------|------|
| ma-1 | 后端：会议行动项完整返回 + synced_to_todo 标记 | feature/ma-1-meeting-action-visible | S2 | 🔵开发中 | 晓伴 | 已分配，待认领；去重逻辑改为标记；见 ma-1.md |
| ma-2 | 前端：会议行动项"已转待办"徽标 | feature/ma-2-synced-badge | S2 | 🔵开发中 | 晓伴 | 已分配，待认领；依赖 ma-1；见 ma-2.md |

---

## 批次六：统一邮件中心联系人复用人员中台（需求3，跨仓库）

> 依赖：人员中台(8001)运行并暴露 staff 列表接口 | 仓库：D:\项目\统一邮件中心\server（独立 git） | 目标：联系人只读复用中台，禁用本地增改删
> ⚠️ 该仓库当前有较多未提交改动（疑似他人在开发），开工前需先 `git stash`/`commit` 自身基线，再切到下列分支。

| task-id | 标题 | 分支(邮件中心仓库) | 级别 | 状态 | 开发者 | 备注 |
|---------|------|------|------|------|--------|------|
| umc-1 | 邮件中心：新增人员中台出站客户端 masterService.ts | feature/umc-1-master-client | S2 | 🔵开发中 | 晓伴 | 已分配，待认领；参考 PMWB backend/master_service.py 契约 |
| umc-2 | 邮件中心：contacts 读路径改中台 + 禁用本地增改删 | feature/umc-2-contacts-from-master | S2 | 🔵开发中 | 晓伴 | 已分配，待认领；依赖 umc-1 |
| umc-3 | 邮件中心前端：通讯录只读展示 | feature/umc-3-contacts-readonly | S2 | 🔵开发中 | 晓伴 | 已分配，待认领；依赖 umc-2 |

---

## 状态枚举
⬜待分配 → 🔵开发中 → 🟡待审查 → 🔴审查退回 → ✅已合入 / ❌已取消

## 任务 Spec 文件
存放于同目录 `.workbuddy/tasks/<task-id>.md`，每个任务一份，自包含全部开发上下文。
