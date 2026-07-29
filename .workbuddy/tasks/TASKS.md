# PMWB 开发任务总表

> 集成者：Vicky2号 | 更新时间：2026-07-28
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

| task-id | 标题 | 分支 | 级别 | 状态 | 开发者 | 备注 |
|---------|------|------|------|------|--------|------|
| db-1 | 引入 ECharts + 封装图表组件 | feature/db-1-echarts | S2 | ✅已合入 | 晓伴→Vicky2号审查 | 0b6bbc0 合入，见 reviews/db-1-R1.md |
| db-2 | 后端 Dashboard 统计接口扩展 | feature/db-2-api | S2 | ✅已合入 | 晓伴→Vicky2号审查 | f6b9406 合入，见 reviews/db-2-R1.md |
| db-3 | 首页 KPI 统计区重构（大数字卡片） | feature/db-3-kpi | S2 | 🔴审查退回 | 晓伴 | ⚠️ P0：直接改旧首页违新旧共存策略，见 reviews/db-3-R1.md |
| db-4 | 首页图表区扩展（柱/线/饼/进度条） | feature/db-4-charts | S2 | 🔴审查退回 | 晓伴 | ⚠️ P0：同 db-3 根因，见 reviews/db-4-R1.md |
| db-5 | 各模块数据可视化卡片 | feature/db-5-modules | S2 | 🔴审查退回 | 晓伴 | ⚠️ P0：同 db-3/4 根因，见 reviews/db-5-R1.md |

---

## 状态枚举
⬜待分配 → 🔵开发中 → 🟡待审查 → 🔴审查退回 → ✅已合入 / ❌已取消

## 任务 Spec 文件
存放于同目录 `.workbuddy/tasks/<task-id>.md`，每个任务一份，自包含全部开发上下文。
