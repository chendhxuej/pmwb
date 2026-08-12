# 🎯 产品经理个人工作台 · UI 设计专项审查报告

| 项目 | 内容 |
|------|------|
| **审查对象** | 产品经理个人工作台（PMWB）前端全部页面 |
| **审查时间** | 2026-08-11 |
| **审查人** | 技术架构师 / UI 设计专家 |
| **前端技术栈** | Vue 3 + Element Plus + Pinia + Vue Router |
| **设计语言** | Bento 网格布局 · 单一蓝色系强调色 `#2f6fed` · 无纯黑 · 精致阴影 |
| **页面数量** | 27 个视图文件 + 22 个组件文件 |
| **核心样式文件** | `design.css`（设计令牌体系）、`main.css`（基础样式） |

---

## 一、项目概览

### 1.1 项目信息

- **页面标题**：产品经理个人工作台
- **项目路径**：`D:\项目\个人工作台系统`
- **前端源码**：`frontend/src/`
- **全局字体**：`'Outfit', 'PingFang SC', 'Microsoft YaHei', 'Helvetica Neue', sans-serif`
- **强调色**：`#2f6fed`（desaturated electric blue）
- **背景色**：`--bg-app: #f3f5f9`
- **文本主色**：`--text-primary: #0f172a`
- **卡片圆角**：`--radius-md: 16px`
- **卡片阴影**：`--shadow-card: 0 2px 12px -3px rgba(15, 23, 42, .08)`

### 1.2 页面清单

| 序号 | 页面/视图 | 路由 | 功能简述 |
|------|----------|------|---------|
| 1 | HomeView | `/dashboard` | 首页看板，KPI + 趋势图 + 待办 + 重点工作 |
| 2 | TaskCenterView | `/task-center` | 任务中心，跨源任务聚合+催办 |
| 3 | RequirementDeliveryView | `/requirement-delivery` | 需求与交付，需求/故事/工单三合一 |
| 4 | OperationLayout | `/operation` | 运营监控布局 |
| 5 | OperationView | `/operation/overview` | 运营总览 |
| 6 | WorkOrderView | `/operation/{bug,data,prod,task,complaint}` | 工单管理（5 类子视图） |
| 7 | ProductionMonitorPlaceholder | `/operation/monitor` | 生产监控（建设中） |
| 8 | MeetingLayout | `/meeting` | 会议日程布局 |
| 9 | MeetingView | `/meeting/list` | 会议列表 + 月历视图 |
| 10 | MeetingActionsView | `/meeting/actions` | 会议行动项管理 |
| 11 | TodoView | `/todo` | 个人待办 |
| 12 | KeyWorkView | `/key-works` | 重点工作 |
| 13 | KnowledgeCenterView | `/knowledge-center` | 知识中心布局 |
| 14 | KnowledgeView | `/knowledge-center/knowledge` | 知识库（Obsidian 联动） |
| 15 | ProductBibleView | `/knowledge-center/product-bible` | 产品圣经 |
| 16 | OperationNotesView | `/knowledge-center/notes` | 知识沉淀 |
| 17 | DomainKnowledgeView | `/knowledge-center/domain` | 按领域浏览 |
| 18 | SqlScriptView | `/knowledge-center/sql-scripts` | SQL 脚本库 |
| 19 | BusinessDomainManage | `/knowledge-center/business-domains` | 业务知识维度 |
| 20 | PersonnelCenterView | `/basic-data` | 人员中台（组织/身份/人员） |
| 21 | WorkReportView | `/work-report` | AI 总结 |
| 22 | LlmProviderManage | `/llm-provider` | 大模型管理 |
| 23 | MailCenterLayout | `/mail-center` | 邮件中心布局 |
| 24 | MailLogsView/MailPlaceholder | `/mail-center/*` | 邮件子页面 |
| 25 | NotFoundView | `/:pathMatch(.*)*` | 404 页面 |
| 26 | RequirementView | 旧路由（兼容） | 需求管理（旧版） |
| 27 | RequirementGroupView | 旧路由（兼容） | 需求分组（旧版） |

### 1.3 核心组件清单

| 组件 | 路径 | 用途 |
|------|------|------|
| MainLayout | `components/Layout/MainLayout.vue` | 侧边栏 + 顶栏 + 路由视图 |
| BentoCard | `components/Common/BentoCard.vue` | Bento 网格卡片基座 |
| DataTable | `components/Common/DataTable.vue` | 表格封装（动态列+分页） |
| SearchForm | `components/Common/SearchForm.vue` | 动态搜索表单 |
| EnlargeInput | `components/Common/EnlargeInput.vue` | 可放大输入框 |
| StatusBadge | `components/Common/StatusBadge.vue` | 状态标签 |
| SuperviseDialog | `components/SuperviseDialog.vue` | 督办弹窗 |
| ChartBar/Line/Pie/Gauge/Progress | `components/Charts/` | VChart 图表封装 |

---

## 二、设计系统评估

### 2.1 设计令牌体系（design.css）⭐⭐⭐⭐

`design.css` 建立了完整的设计令牌体系，覆盖以下维度：

| 维度 | 状态 | 评价 |
|------|------|------|
| 颜色系统 | ✅ 完整 | 主色、辅助色、语义色、软色均有定义 |
| 间距系统 | ⚠️ 部分 | 存在 `mt-16` 等工具类，但无系统化 `spacing` 比例尺 |
| 字体系统 | ✅ 完整 | `--font-display` + `--font-mono`，含 fallback 栈 |
| 圆角体系 | ✅ 完整 | 三级圆角：`sm: 10px` / `md: 16px` / `lg: 22px` |
| 阴影体系 | ✅ 完整 | 普通态 `--shadow-card` + 抬高态 `--shadow-elevated` |
| 过渡动画 | ✅ 完整 | `--transition-fast: .18s cubic-bezier(.4, 0, .2, 1)` |
| 自定义组件样式 | ✅ 丰富 | `pm-tag` / `pm-btn` / `pm-step` / `pm-table-wrap` 等 |
| Element Plus 覆盖 | ✅ 完整 | 主色、圆角、卡片样式均已覆盖 |

### 2.2 main.css 遗留问题 ⚠️

`main.css` 存在与 `design.css` 不一致的遗留样式：

- `border-radius: 4px` 硬编码（design.css 为 10px/16px）
- `.search-form { background: #fff; border-radius: 4px }` 与 Bento 卡片风格脱节
- `.table-card { background: #fff; border-radius: 4px }` 同上
- 全局字体未引用 `--font-display` 变量
- `#303133` 主色与 design.css 的 `--text-primary: #0f172a` 不一致

### 2.3 布局系统评估

| 布局模式 | 使用页面 | 评价 |
|---------|---------|------|
| Bento Grid（12 列） | HomeView, MeetingView, KeyWorkView | ✅ 高品质，入场动画精致 |
| el-row el-col | WorkOrderView | ⚠️ 未使用 Bento，布局不一致 |
| flex-wrap | TaskCenterView 统计行 | ⚠️ 非网格弹性布局 |
| 普通页面容器 | RequirementDeliveryView, PersonnelCenterView 等 | ⚠️ 无 Bento 网格 |

### 2.4 侧边栏导航评估

MainLayout.vue 的侧边栏设计品质较高：

- ✅ 两级菜单（父/子）层级清晰，子项视觉弱化处理
- ✅ 选中态左侧蓝色彩条（`.nav-bar`）+ 背景色高亮
- ✅ 折叠态可保留图标访问
- ✅ 二级菜单展开过渡动画（`nav-expand`）
- ❌ 折叠态二级菜单完全隐藏，无 Flyout 弹出
- ✅ 图标调色板循环分配，视觉丰富

---

## 三、问题汇总（按页面）

### 3.1 首页（HomeView）

| 问题 | 严重程度 | 说明 |
|------|---------|------|
| 趋势图 SVG 在图外嵌入渲染 | 低 | 纯 JavaScript 计算坐标，无封装组件 |
| "陈工" 用户名为硬编码 Demo 数据 | 低 | 需替换为真实用户数据 |
| KPI 无微交互 | 低 | 数字缺少计数动画 |

### 3.2 需求页面

| 页面 | 问题 | 严重程度 |
|------|------|---------|
| RequirementView | Expand Row 嵌套子表格缺少视觉连线 | 中 |
| RequirementView | 展开/收起无过渡动画 | 中 |
| RequirementDeliveryView | el-tabs + el-table 组合良好，但搜索工具栏混用 | 低 |
| RequirementDeliveryView | 自定义 `pm-tag` 与 `el-tag` 混用 | 低 |

### 3.3 任务与工单页面

| 页面 | 问题 | 严重程度 |
|------|------|---------|
| TaskCenterView | 统计卡未使用 `kpi-card` 规范 | 高 |
| TaskCenterView | 内容较长，缺少「返回顶部」按钮 | 低 |
| WorkOrderView | `el-row :gutter="12"` 非 Bento 布局 | 中 |
| WorkOrderView | 8 个统计列在大屏偏宽小屏溢出 | 中 |
| TodoView | 搜索表单使用传统 `el-form :inline`，非紧凑工具栏 | 低 |

### 3.4 会议页面

| 问题 | 严重程度 | 说明 |
|------|---------|------|
| MeetingView 月历视图品质高 | ✅ | 最佳页面之一 |
| MeetingView 列表视图 `el-table` 的 `@row-click` 与 `@click.stop` 冲突风险 | 低 | 操作列需处理事件冒泡 |
| MeetingActionsView 使用 `el-card shadow="never"` + 表格 | 低 | 与外层容器层级可优化 |

### 3.5 知识中心与邮件中心

| 页面 | 问题 | 严重程度 |
|------|------|---------|
| KnowledgeView 卡片网格布局精致 | ✅ | |
| KnowledgeView 目录树 `kv-tree` 在窄屏可能溢出 | 低 | |
| ProductBibleView 目录树 + Markdown 渲染品质高 | ✅ | 最佳页面之一 |
| MailCenterLayout 使用 `padding: 16px` 硬编码 | 低 | |

### 3.6 人员中台

| 问题 | 严重程度 | 说明 |
|------|---------|------|
| PersonnelCenterView 使用 `:empty-text` 而非 `el-empty` | 低 | 空状态不一致 |

---

## 四、优化建议（8 条）

### 🔴 P0 — 高优先级

---

#### 建议 #1：消除 main.css 与 design.css 的样式断层

**文件：** `main.css` → 合并至 `design.css`

**问题定位：**
`main.css` 保留着 Element Plus 默认残留样式（`border-radius: 4px`、`background: #fff`），与 design.css 定义的 Bento 设计语言（`--radius-md: 16px`、`--shadow-card`）不一致。首页与列表页之间存在视觉断层——用户从 HomeView 进入任何列表页都会感受到设计语言切换。

**解决方案：**

```css
/* 迁移前 — main.css */
.search-form { background: #fff; padding: 20px; border-radius: 4px; }
.table-card { background: #fff; padding: 20px; border-radius: 4px; }

/* 迁移后 — 统一复用 design.css 设计令牌 */
.page-container {
  padding: 20px;
  /* 移除自身背景和圆角，由内部卡片/容器承担 */
}
```

需确保：
1. 所有 `border-radius: 4px` 替换为 `var(--radius-md)` 或 `var(--radius-sm)`
2. 白色背景卡片统一使用 `class="card"` 或 `class="pm-table-wrap"`
3. `main.css` 中有效的全局样式迁移至 `design.css` 后删除该文件

**预估工作量：** ⭐⭐⭐ 中（1-2 天）  
**影响范围：** 所有 27 个视图文件

---

#### 建议 #2：全站 KPI 统计卡片统一设计规范

**文件：** TaskCenterView, WorkOrderView, TodoView, MeetingView, KeyWorkView, RequirementDeliveryView 等

**问题定位：**
`design.css` 已定义 `kpi-card / kpi-num / kpi-label` 样式体系（monospace 等宽数字 34px 800w、语义色变体），但仅首页 HomeView 采用。其余 8+ 页面各自编写了 `.stat-card / .stat-value / .stat-label`，存在：
- 数字无统一 font-family `var(--font-mono)`
- 状态颜色硬编码而非 CSS 变量
- 布局使用 `el-row` / `flex-wrap` 而非 Bento Grid

**解决方案：**
```html
<!-- 改造前 — 各自自定义 -->
<el-card class="stat-card">
  <div class="stat-value">{{ stats.total }}</div>
  <div class="stat-label">全部待办</div>
</el-card>

<!-- 改造后 — 统一复用 design.css -->
<section class="card kpi-card">
  <div class="kpi-num blue">{{ stats.total }}</div>
  <div class="kpi-label">全部待办</div>
</section>
```

外层容器改用 `bento-grid` 替代 `el-row` / `flex-wrap`：
```html
<div class="bento-grid kpi-strip">
  <!-- 每个 kpi-card 在 grid 中 span="3" -->
</div>
```

**预估工作量：** ⭐⭐ 低（0.5-1 天）  
**影响页面：** 8+ 页面

---

### 🟡 P1 — 中优先级

---

#### 建议 #3：Skeleton 骨架屏替代 v-loading 覆盖层

**文件：** 所有使用 `v-loading` 的表格/列表页面（10+ 页）

**问题定位：**
`v-loading` 遮罩完全遮挡表格区域，加载完成时内容"闪烁"出现。现代产品（Notion、Linear）均采用骨架屏占位，加载完成后淡入衔接。

**解决方案：**
```html
<!-- 改造前 -->
<el-table v-loading="loading" :data="tableData" ...>

<!-- 改造后 -->
<template v-if="loading">
  <el-skeleton :rows="6" animated class="sk-table" />
</template>
<template v-else>
  <el-table :data="tableData" ...>
</template>
```
```css
/* design.css 新增骨架屏动画 */
@keyframes skeleton-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
.sk-table { animation: skeleton-pulse 1.5s ease-in-out infinite; }
```

**预估工作量：** ⭐⭐⭐ 中（2-3 天）  
**影响页面：** 10+ 页面

---

#### 建议 #4：统一 Dialog / Drawer 使用协议

**文件：** RequirementView, TaskCenterView, MeetingView, PersonnelCenterView 等

**问题定位：**
项目混用 `el-dialog` 居中浮层和 `el-drawer` 右侧滑入抽屉，使用场景无显式约定：详情查看有的用 Dialog、有的用 Drawer；编辑表单有的用 Drawer、有的用 Dialog。用户无法预测弹窗交互模式。

**解决方案：**

| 场景 | 应使用 | 参数标准 |
|------|--------|---------|
| 信息详情查看 | `el-drawer` | `size="70%" direction="rtl"` |
| 编辑/新建表单 | `el-dialog` | `width="600px" :close-on-click-modal="false"` |
| 确认操作 | `el-dialog` | `width="420px" :show-close="true"` |

统一定义过渡动画：
```css
.el-dialog, .el-drawer {
  transition: all var(--transition-fast);
}
```

**预估工作量：** ⭐⭐ 低（1 天）  
**影响组件：** 5+ 页面

---

#### 建议 #5：优化 Expand Row 展开行的视觉层次

**文件：** `RequirementView.vue`

**问题定位：**
需求管理页面使用 `el-table type="expand"`，展开行内嵌套完整子表格。缺少视觉连线、层级背景色和展开过渡动画，用户容易丢失上下文。

**解决方案：**
1. 展开行左侧绘制连接线（父行箭头 → 展开区域）
2. 子表格改用 `el-card shadow="never"` 平铺
3. 展开过渡：`<transition name="el-zoom-in-top">`
4. 展开区域背景：`var(--border-subtle)` + 左侧缩进 32px

**预估工作量：** ⭐⭐⭐ 中（1-2 天）  
**直接影响：** RequirementView（核心页面）

---

### 🟢 P2 — 低优先级

---

#### 建议 #6：统一空状态系统

**文件：** 所有 27 个视图

**问题定位：**
空状态碎片化：`el-empty` / `:empty-text` / `.empty-hint` / 纯文本混用，无统一插画和引导操作。

**解决方案：**
```html
<el-empty :image="customEmptySvg" description="暂无待办事项">
  <el-button type="primary" @click="handleCreate">创建第一个待办</el-button>
</el-empty>
```
全局覆盖 `el-empty` 样式使其对齐设计语言，并在 `design.css` 中提供 `.empty-state` 占位类。

**预估工作量：** ⭐⭐ 低（1 天）  
**影响页面：** 全部 27 页

---

#### 建议 #7：侧边栏折叠态添加 Flyout 弹出子菜单

**文件：** `MainLayout.vue`

**问题定位：**
折叠态二级菜单完全隐藏，运营监控（5 个子项）和知识中心（6 个子项）等多子页面模块在折叠态下无法导航。

**解决方案：**
```css
.sidebar.collapsed .nav-block:hover .nav-children {
  display: flex;
  flex-direction: column;
  position: absolute;
  left: 64px; top: 0;
  width: 200px;
  background: #fff;
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-elevated);
  padding: 8px;
}
```

**预估工作量：** ⭐⭐⭐ 中（1-2 天）  
**影响组件：** MainLayout.vue

---

#### 建议 #8：搜索表单标准化

**文件：** MeetingView, TaskCenterView, TodoView, RequirementView, WorkOrderView, RequirementDeliveryView 等

**问题定位：**
6+ 页面各有不同的搜索模式（el-form inline / 扁平工具栏 / 自定义 SearchForm 组件），视觉和交互不一致。

**解决方案：**
标准化为两种模式：
1. **紧凑工具栏**（1 行）：`EnlargeInput` + 1-2 个 `el-select` + 查询按钮
2. **完整展开模式**（复杂场景）：保留 `el-form :inline` 但统一圆角/间距

搜索输入框统一 `prefix-icon="Search"`，按钮统一 `size="small"`。

**预估工作量：** ⭐⭐ 低（1 天）  
**影响页面：** 6+ 页面

---

## 五、总体评分

| 维度 | 评分（满分 10） | 评语 |
|------|---------------|------|
| 设计语言一致性 | 6.5 | design.css 体系优秀，但 main.css 残留导致断层 |
| 色彩系统应用 | 8.0 | 单蓝色系把控到位，语义色体系完整 |
| 布局合理性 | 7.5 | Bento Grid 品质高，但部分页面未使用 |
| 交互流畅度 | 7.0 | 过渡动画存在但部分场景缺失 |
| 操作便捷性 | 7.5 | 侧边栏+面包屑导航良好，折叠态有短板 |
| 空状态处理 | 4.0 | 碎片化严重，需统一 |
| 加载体验 | 5.5 | v-loading 落后，缺少骨架屏 |
| 响应式适配 | 5.0 | 暂未发现明显响应式处理（需进一步审查） |
| 无障碍设计 | 4.0 | 缺少 aria 标签、键盘导航测试（待专项审查） |
| 组件封装复用 | 8.0 | BentoCard/DataTable/StatusBadge 等封装良好 |

### 综合评分：**6.3 / 10**

---

## 六、优先级建议路线图

```
Sprint 1（P0）：样式断层修复 + KPI 卡片统一
  ├── #1 合并 main.css → design.css
  └── #2 全站 KPI 卡片规范统一

Sprint 2（P1）：加载体验 + 交互规范
  ├── #3 Skeleton 骨架屏
  ├── #4 Dialog/Drawer 协议统一
  └── #5 Expand Row 层次优化

Sprint 3（P2）：体验细节打磨
  ├── #6 空状态系统统一
  ├── #7 侧边栏 Flyout 菜单
  └── #8 搜索表单标准化
```

---

## 七、附录：设计变量速查表

| 变量 | 值 | 用途 |
|------|-----|------|
| `--bg-app` | `#f3f5f9` | 应用背景色 |
| `--accent` | `#2f6fed` | 主强调色 |
| `--text-primary` | `#0f172a` | 主文本色 |
| `--text-secondary` | `#64748b` | 次要文本色 |
| `--radius-md` | `16px` | 卡片圆角 |
| `--shadow-card` | `0 2px 12px -3px rgba(15,23,42,.08)` | 卡片阴影 |
| `--transition-fast` | `.18s cubic-bezier(.4,0,.2,1)` | 标准过渡 |
| `--font-display` | `'Outfit', 'PingFang SC', ...` | 显示字体 |
| `--font-mono` | `'JetBrains Mono', ...` | 等宽字体 |
| `--sidebar-w` | `220px` | 侧边栏宽度 |

---

*本报告基于对全部 27 个视图文件和 22 个组件文件的完整审查生成。每条建议均包含问题定位、可执行方案和预期效果，可直接交由前端工程师排期实施。*
