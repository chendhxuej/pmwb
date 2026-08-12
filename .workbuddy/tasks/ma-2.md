# ma-2 前端：会议行动项"已转待办"徽标

## 背景上下文
配合 ma-1：会议行动项来源现在返回全部行动项，并带 `synced_to_todo` 标记。本任务在任务中心列表（尤其"会议行动项"标签）对 `synced_to_todo=true` 的行展示"已转待办"徽标，避免误以为数据丢失。

## 精确改动范围
文件：`frontend/src/views/TaskCenterView.vue`
- 在任务行渲染处（标题列或操作列附近）依 `row.synced_to_todo` 显示 `<el-tag size="small" type="success">已转待办</el-tag>`。
- 该标记对所有来源通用（只有 meeting_action 会有 true），可放在通用渲染。
- "编辑"按钮深链仍指向 `/meeting?actionId=`（tc-1/tc-3）。

## 可执行验收命令
- 已同步的会议行动项显示"已转待办"徽标；未同步不显示。
- `vitest` + `vite build` 通过；浏览器冒烟确认。

## 禁止项清单
- 不改后端（那是 ma-1）。
- 不隐藏/过滤已同步项。

## 依赖
ma-1（后端字段）。

## 起点指引
读 `TaskCenterView.vue` 表格列渲染(124-162)与 detail 抽屉。
