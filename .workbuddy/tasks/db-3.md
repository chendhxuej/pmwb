# db-3：首页 KPI 统计区重构（大数字卡片）

## 状态

- **Status**: 🟡待审查
- **Branch**: feature/db-3-kpi
- **Commit**: 3368e0e
- **Developer**: 晓伴
- **Reviewer**: Vicky2号

## 交付内容

### 新增文件

| 文件 | 说明 |
|:-----|:------|
| `frontend/src/components/Dashboard/KpiCard.vue` | 大数字 KPI 卡片组件（支持 title/value/unit/trend/color/icon/progress），含 hover 上浮效果 |
| `frontend/src/components/Dashboard/KpiCardRow.vue` | 响应式 KPI 卡片行容器（支持 title/columns），大屏按列数、中屏减半、小屏2列 |

### 修改文件

| 文件 | 说明 |
|:-----|:------|
| `frontend/src/views/HomeView.vue` | 替换旧 BentoCard KPI 区 → KpiCardRow + KpiCard；新增 module_stats 模块统计卡片区（来自 db-2 扩展） |

### 自测

```
vite build: ✅ built in 46.56s
vitest run: ✅ 4 passed (2 files)
```

### 取值逻辑

- **KPI 卡片**：来自 `mergeDashboard(res.kpis)`，数据仍由后端 `get_kpis()` 提供
- **模块统计卡片**：来自 `res.module_stats`（db-2 扩展字段），未接入时静默隐藏
- 所有字段均防御式处理，后端缺字段回退 demo 数据

### 卡片展示项

| 卡片组 | 来源 | 示例卡片 |
|:-------|:-----|:---------|
| 顶部 KPI | `res.kpis` | 我的待办、本周新增需求、进行中工单、运营预警 |
| 模块统计 | `res.module_stats` | 需求总数/本周新增、工单总数/已解决、运营问题、本周会议、知识条目、今日发信 |
