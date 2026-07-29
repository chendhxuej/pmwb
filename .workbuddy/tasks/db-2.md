# db-2：后端 Dashboard 统计接口扩展

## 状态

- **Status**: 🟡待审查
- **Branch**: feature/db-2-api
- **Commit**: ff4377a
- **Developer**: 晓伴
- **Reviewer**: Vicky2号

## 交付内容

### 后端

| 变更项 | 说明 |
|:-------|:-----|
| `schemas/dashboard.py` | 新增 `ModuleStats`（含6个子级）、`TrendPoint`、`DistributionItem`、`ProgressItem`，`DashboardData` 新增 4 个可选字段 |
| `services/dashboard.py` | 新增 4 个方法，已接入 `get_dashboard()` |
| `tests/test_dashboard.py` | 从 1 扩展为 5 个测试用例 |

### Schema 扩展字段

```
module_stats: Optional[ModuleStats]         # 6 模块统计卡片
trend_charts: Optional[dict]                # 需求/问题/工单 近7天趋势
distribution_charts: Optional[dict]         # 需求状态/问题类型/工单优先级 分布
progress_items: Optional[dict]              # 重点任务进度
```

### 自测

```
tests/test_dashboard.py::test_dashboard_stats              ✅
tests/test_dashboard.py::test_dashboard_module_stats       ✅
tests/test_dashboard.py::test_dashboard_trend_charts       ✅
tests/test_dashboard.py::test_dashboard_distribution_charts ✅
tests/test_dashboard.py::test_dashboard_progress_items     ✅
全量后端（排除预存 fail tests/basic_data + product_bible）: 75 passed
```
