## 修复回复

### P0-1 — 二次解包

- **根因**：`KeyWorkView.vue` 中 `kwApi.findKeyWorkByChild()` 返回的数据已被 axios 响应拦截器（`request.js`）解包一次，但代码又访问了 `res.data?.data`，造成二次解包
- **修复**：改为直接访问 `res?.key_work_id` 和 `detail`（拦截器已解包，axios 响应体自动转换），见 `e0b837f`
- **提交**：`60e05d8` (tc-3 fix commit, 含 KeyWorkView.vue 改动)

### P0-2 — TodoView 无独立路由

- **根因**：router 中未注册 `/todo` 路由，`/todo?id=xxx` 不匹配任何页面
- **修复**：在 `router/index.js` 的 Dashboard children 中添加了 `path: 'todo' → TodoView` 的路由条目
- **提交**：`60e05d8`

### P1-1 — 分支基线含 .workbuddy 改动

- **根因**：首 commit `24e6f2e`（误标为 chore 但实际包含了前端深链代码）引入了 `.workbuddy/` 和 `dashboard.py/DashboardV2View` 等无关文件
- **修复**：重建分支，基于 origin/main 通过 cherry-pick 只提取 `78df319`（后端 by-child）和手动重写 4 视图深链代码，跳过 `24e6f2e` 的 .workbuddy/dashboard 改动。最终 diff 无 `.workbuddy/` 文件
- **分支提交历史**（3 commits）：

  | Commit | 来源 | 内容 |
  |:-------|:-----|:------|
  | 90ac5c6 | local main | 基线（ma-2 合并） |
  | c28ce14 | cherry-pick 78df319 | 后端 by-child 端点 + api + KeyWorkView 深链 |
  | 60e05d8 | 手动重写 | 4 视图深链 + /todo 路由 + 二次解包修复 |

### P2-1 — RequirementDeliveryView setTimeout 不可靠

- **根因**：原代码 `setTimeout(applyDeepLink, 300)` 依赖 300ms 硬编码延迟，数据加载未完成时深链失效
- **修复**：`loadRequirements()` / `loadTickets()` 从顶层调用移至 `onMounted(async () => { await ...; applyDeepLink() })`，确保数据加载完成后再执行深链定位
- **提交**：`60e05d8`

## 修复状态

| 问题 | 严重度 | 状态 | 提交 |
|:-----|:-------|:-----|:-----|
| P0-1 KeyWorkView 二次解包 | P0 | ✅ 已修复 | 60e05d8 |
| P0-2 TodoView 无独立路由 | P0 | ✅ 已修复 | 60e05d8 |
| P1-1 分支基线不干净 | P1 | ✅ 已修复 | 分支重建，跳过 24e6f2e |
| P2-1 setTimeout 不可靠 | P2 | ✅ 已修复 | 60e05d8 |
