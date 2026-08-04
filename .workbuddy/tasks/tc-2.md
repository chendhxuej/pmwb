# tc-2 前端：任务中心操作列新增"编辑"按钮

## 背景上下文
同上（需求1）。前端已有 `gotoSource(task)`（`TaskCenterView.vue:377`），但仅详情抽屉里有"前往源模块"按钮（line 206）。操作列（line 156-162）只有 详情/催办/通知。本任务在操作列加"编辑"按钮，点击直接 `gotoSource(row)` 深链跳转（URL 由 tc-1 提供）。

## 精确改动范围
文件：`frontend/src/views/TaskCenterView.vue`
- 在操作列 `<template #default="{ row }">`（line 157-161）新增 `<el-button link type="primary" size="small" @click="gotoSource(row)">编辑</el-button>`。
- 保留现有 详情/催办/通知 按钮。
- 确认 `gotoSource` 已 `drawerVisible.value=false` 后 `router.push(task.source_url)`（line 377-380）——无需改，复用即可。

## 可执行验收命令
- `cd frontend && npx vitest run` 相关用例通过（如有 TaskCenterView 测试）。
- `npm run build`（vite build）干净。
- 浏览器冒烟：任务中心任一来源行点"编辑"→ 跳到来源模块且能定位到该工单（依赖 tc-1 深链 + tc-3 模块支持）。

## 禁止项清单
- 不在任务中心内联编辑（保持跳转语义）。
- 不改动其他来源逻辑/聚合。

## 起点指引
读 `TaskCenterView.vue` 操作列(156-162)与 `gotoSource`(377-380)。依赖 tc-1 提供深链 URL。
