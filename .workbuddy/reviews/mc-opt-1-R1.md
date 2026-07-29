# 审查反馈：mc-opt-1 — 邮件统计概览卡片

- **分支**：feature/mc-opt-1-stats
- **审查日期**：2026-07-29
- **审查结果**：✅ 通过（可直接合入）

## 变更概要

- 后端 `/mail-center/stats`：聚合 PMWB email_records + mail-center(3210) 账号/联系人/模板数量
- 前端 `MailStatsOverview.vue`：7 个 KPI 卡片横排，hover 上浮动效
- 测试：5 个 pytest 用例 + EmailRecordFactory
- 质量门禁：backend pytest 6/6 全绿, vite build 干净

## 发现的问题

### P2 — 1 个

| 问题 | 说明 | 建议 |
|------|------|------|
| hover 动效不生效 | `cards` 是 computed 返回的普通对象数组，`card.hover = true` 修改非 reactive 属性不会触发 DOM 更新 | 改用 `reactive` 数组，或用 CSS `:hover` 替代 |

### 改进建议

- `trend` 字段在所有卡片中均为 `null`，趋势显示代码为死代码。建议后续接入真实环比数据时启用，或先移除 v-if 块减少混淆。

## 项目约定引用

- 邮件中心聚合原则：PMWB 只做邮件中心不具备的增值能力（统计概览属于此类）

---

## 开发者回复区

### 修复记录

| 日期 | 修复说明 | 提交 SHA | 审查确认 |
|------|---------|----------|---------|
| — | — | — | — |
