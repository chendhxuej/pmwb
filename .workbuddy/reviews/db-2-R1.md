# 审查反馈：db-2 — 后端 Dashboard 统计接口扩展

- **分支**：feature/db-2-api
- **审查日期**：2026-07-29
- **审查结果**：✅ 通过（可直接合入）

## 变更概要

- Schema 扩展：ModuleStats（6 子模块）/ TrendPoint / DistributionItem / ProgressItem
- Service 新增 4 个方法：get_module_stats / get_trend_charts / get_distribution_charts / get_progress_items
- get_dashboard() 集成新字段
- 测试：5 个新 pytest 用例
- 质量门禁：backend pytest 6/6 全绿

## 发现的问题

无 P0/P1 问题。

### P2 — 1 个

| 问题 | 说明 | 建议 |
|------|------|------|
| `email_7d_start` 计算晦涩 | `ws_utc - timedelta(days=7 - (week_start - today).days)` 逻辑正确但绕弯，读起来像 bug | 简化为 `today_start_utc - timedelta(days=7)`，意图更清晰 |

### 改进建议

- 分布数据的中文标签 map（`_REQ_STATUS_LABEL` 等）定义在方法内部，建议抽到模块级常量，方便复用
- `get_trend_charts()` 中 `ticketsTrend` 按 `go_live_date` 统计可能不符合"活跃趋势"语义，建议确认业务含义

---

## 开发者回复区

### 修复记录

| 日期 | 修复说明 | 提交 SHA | 审查确认 |
|------|---------|----------|---------|
| — | — | — | — |
