# Task Spec: db-1 — 引入 ECharts 图表库 + 封装图表组件

## 背景上下文
当前首页看板使用手写 SVG 绘制图表（面积图+甜甜圈），功能简陋且维护成本高。参考截图需要丰富的图表类型（柱状图、折线图、饼图、进度条等），需引入专业图表库。

## 改动范围

### 前端
1. **安装 ECharts**
   - `npm install echarts vue-echarts`
   - 或使用 CDN 方式按需引入（减少包体积）
2. **封装通用图表组件**
   - `frontend/src/components/Charts/ChartLine.vue` — 折线图（支持多线、面积填充）
   - `frontend/src/components/Charts/ChartBar.vue` — 柱状图（支持分组、堆叠）
   - `frontend/src/components/Charts/ChartPie.vue` — 饼图/环形图（支持图例、tooltip）
   - `frontend/src/components/Charts/ChartGauge.vue` — 仪表盘（用于成功率等百分比）
   - `frontend/src/components/Charts/ChartProgress.vue` — 进度条（水平条形进度）
3. **统一图表主题**
   - 定义 PMWB 图表配色方案（参考截图浅蓝色系）
   - 主色：`#2f6fed`（蓝）、`#0f9d6b`（绿）、`#d98a1f`（橙）、`#e02424`（红）
   - 背景透明，文字色适配 dark/light 主题
4. **全局注册**
   - 在 main.js 中注册 vue-echarts 组件

## 验收命令
```bash
cd frontend && npm install echarts vue-echarts
cd frontend && npx vite build 2>&1 | tail -3
# 确认 build 无报错，包体积增加 < 200KB（gzip）
cd frontend && npx vitest run 2>&1 | tail -3
```

## 禁止项
- 不要全量引入 echarts（`import * as echarts from 'echarts'`），使用按需引入
- 不要修改现有 HomeView.vue（本任务只封装组件，不替换页面）
- 不要在封装组件中耦合业务数据逻辑（组件只接收 props）

## 起点指引
- 前端入口：`frontend/src/main.js`
- 组件目录：`frontend/src/components/Charts/`（新建）
- ECharts 按需引入文档：https://echarts.apache.org/handbook/zh/basics/import
