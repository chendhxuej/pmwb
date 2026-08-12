# Task Spec: db-4 — 首页图表区扩展（柱状图、折线图、饼图、进度条）

## 背景上下文
参考截图中部有丰富的图表区域：AI 价值运营趋势（柱状+折线组合）、智能资产矩阵（环形图）、流程改造全景（进度条）。当前 PMWB 首页只有一个简单面积图和一个甜甜圈图，需要大幅扩展。

## 改动范围

### 前端
1. **修改 HomeView.vue — 图表区域重构**
   - **Row 1: 趋势组合图**（替换现有趋势面积图）
     - 使用 ChartBar + ChartLine 组合展示「近7天各模块活跃趋势」
     - X轴：日期；Y轴：数量
     - 系列：需求新增量（柱状）、工单完成量（柱状）、运营问题（折线）
     - 数据来自 db-2 扩展的 `trend_charts`
   - **Row 2: 分布饼图组**（替换现有甜甜圈图或并排放置）
     - 3个饼图并排：需求状态分布、工单状态分布、运营问题类型分布
     - 使用 ChartPie 组件
     - 数据来自 db-2 扩展的 `distribution_charts`
   - **Row 3: 进度条区**（新增，参考截图底部）
     - 展示「重点任务与风险」或「重点工作进度」
     - 使用 ChartProgress 组件
     - 数据来自 db-2 扩展的 `progress_items`
2. **布局调整**
   - 使用 CSS Grid 或 Flex 实现响应式图表布局
   - 大屏（>1280px）：图表并排；小屏：堆叠

## 验收命令
```bash
cd frontend && npx vite build 2>&1 | tail -3
cd frontend && npx vitest run 2>&1 | tail -3
# 浏览器访问 /dashboard，确认图表正常渲染
```

## 禁止项
- 不要修改后端接口（复用 db-2 数据）
- 不要删除现有的趋势图和甜甜圈图的逻辑（如果后端数据缺失，优雅降级显示 demo 数据）
- 图表组件内部不要耦合业务逻辑

## 起点指引
- 首页看板：`frontend/src/views/HomeView.vue`
- 图表组件：`frontend/src/components/Charts/`（db-1 封装）
- 数据接口：db-2 扩展后的 `/dashboard` 响应
