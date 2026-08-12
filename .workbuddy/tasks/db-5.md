# Task Spec: db-5 — 各模块数据可视化卡片（需求趋势、工单分布、会议统计等）

## 背景上下文
参考截图底部有多个信息卡片：流程改造全景（进度条）、重点任务与风险（列表+状态标签）、重点场景运行态势（排名列表）。当前 PMWB 首页有「最近需求」「今日日程」等列表，但缺少模块级的深度可视化。

## 改动范围

### 前端
1. **新增组件** `frontend/src/components/Dashboard/ModuleStatCard.vue`
   - 通用模块统计卡片容器：标题 + 右上角「更多」链接 + 内容区
   - 支持多种内容模式：列表、进度条、排名、迷你图表
2. **新增各模块可视化卡片**
   - `RecentRequirementsCard.vue` — 最近需求（优化现有表格，增加状态色条+进度指示）
   - `TicketProgressCard.vue` — 工单进度（进度条展示各工单完成度）
   - `IssueAlertCard.vue` — 运营预警（带严重级别色标的列表）
   - `MeetingTimelineCard.vue` — 今日日程（时间轴形式）
   - `TodoPriorityCard.vue` — 我的待办（优先级色块+进度环）
   - `MailQuickStatCard.vue` — 邮件中心快捷统计（今日发送数+成功率迷你图）
3. **修改 HomeView.vue**
   - 在图表区下方增加「模块详情区」
   - 使用 Grid 布局，2~3列排列各模块卡片
   - 每个卡片独立加载数据（已有 dashboard API 统一返回，前端按需取用）
4. **视觉统一**
   - 所有卡片统一圆角、阴影、背景色
   - 参考截图浅蓝色系：`#f0f7ff` 背景、`#2f6fed` 强调色

## 验收命令
```bash
cd frontend && npx vite build 2>&1 | tail -3
cd frontend && npx vitest run 2>&1 | tail -3
# 浏览器访问 /dashboard，确认各模块卡片展示正常
```

## 禁止项
- 不要新增后端接口（复用 db-2 扩展后的数据）
- 不要修改各模块的原有独立页面（只影响首页看板）
- 卡片内容不要写死数据，必须支持 API 数据驱动

## 起点指引
- 首页看板：`frontend/src/views/HomeView.vue`
- 当前列表组件：RecentReqs、Todos、Alerts、Schedule（均在 HomeView 内）
- 样式参考：截图中底部信息卡片风格
