# 审查反馈：db-3 — KPI 统计区重构（大数字卡片）

- **分支**：feature/db-3-kpi
- **审查日期**：2026-07-29
- **审查结果**：🔴 退回（P0 需修复）

## 变更概要

- 新增 `KpiCard.vue`：大数字卡片组件（颜色主题/趋势箭头/进度条/数字格式化）
- 新增 `KpiCardRow.vue`：卡片行布局组件（响应式列数）
- 修改 `HomeView.vue`：用 KpiCard 替换旧 KPI 区域

## 发现的问题

### P0 — 必须修复

| # | 问题 | 说明 | 修复要求 |
|---|------|------|---------|
| 1 | **直接修改旧首页，违反「新旧共存」策略** | 批次三 Spec 明确要求：新页面走 `/dashboard-v2` 路由，旧 `HomeView（/）` 保持不动。当前实现直接改了 `HomeView.vue` | 创建 `DashboardV2View.vue`，新增路由 `/dashboard-v2`，将 KpiCard 等新组件用于新页面，保持 `HomeView.vue` 不变 |

### P2 — 改进建议

- `msCards` 中的 `trend` 全为 `null`，趋势箭头不会显示；建议接入真实环比数据或移除 null 赋值

---

## 开发者回复区

### 修复记录

| 日期 | 修复说明 | 提交 SHA | 审查确认 |
|------|---------|----------|---------|
| 2026-07-29 | P0: 创建 DashboardV2View.vue + /dashboard-v2 路由，还原 HomeView 不变；KpiCard/KpiCardRow 移入新页面 | c2430e6 | 待确认 |
| 2026-07-29 | P2: msCards trend 保留 null 作为占位，待 db-2 合入后接入真实数据 | — | 待确认 |
