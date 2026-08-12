## 修复回复（第二轮）

### P0-1 — KeyWorkView 二次解包未真修复 ❌

R1 已指出该问题，晓伴回复"改为直接访问 res?.key_work_id（拦截器已解包）"。但 R2 实测分支 `feature/tc-3-module-deeplink` 上 `KeyWorkView.vue` 第 868-885 行的代码仍是：

```js
const res = await kwApi.findKeyWorkByChild(type, childId)
const kwId = res.data?.data?.key_work_id  // ← 二次解包，未改
if (kwId) {
  const detail = await kwApi.getKeyWork(kwId)
  if (detail.data?.data) await openDetail(detail.data.data)  // ← 二次解包，未改
}
```

R1 修复记录与实际 diff 不一致——只新增了 `useRoute` + `route.query.id` 解析逻辑，但**未触及二次解包**。request.js 拦截器已把 `code===0` 的响应解包为 `data.data`，所以这里 `res.data?.data` 永远是 undefined，`kwId` 为 null → 重点工作深链完全失效（用户在任务中心点"编辑"跳到 KeyWorkView 找不到对应记录）。

### P0-2 — TodoView 路由注册 ✅ 已修复

`router/index.js` 添加了 `path: 'todo' → TodoView` 条目，详见 `60e05d8`。

### P2-1 — setTimeout 不可靠 ✅ 已修复

`RequirementDeliveryView` 已改为 `onMounted(async () => { await loadRequirements(); await loadTickets(); applyDeepLink() })`，确保数据加载完成后再深链定位。

### 分支基线 ✅ 已清理

分支已重建（cherry-pick 78df319 + 手动重写 60e05d8），无 `.workbuddy/` 无关文件。

## 修复状态

| 问题 | 严重度 | R1 状态 | R2 实测 | 提交 |
|:-----|:-------|:--------|:--------|:-----|
| P0-1 KeyWorkView 二次解包 | P0 | 声称已修复 | ❌ **未真修复** | 60e05d8 未触及 |
| P0-2 TodoView 无独立路由 | P0 | ✅ | ✅ | 60e05d8 |
| P1-1 分支基线不干净 | P1 | ✅ | ✅ | 分支重建 |
| P2-1 setTimeout 不可靠 | P2 | ✅ | ✅ | 60e05d8 |

## 重做要求

**P0-1 修复示例**（KeyWorkView.vue line ~880）：

```js
const res = await kwApi.findKeyWorkByChild(type, childId)
const kwId = res?.key_work_id  // 拦截器已解包，res 直接是 data.data
if (kwId) {
  const detail = await kwApi.getKeyWork(kwId)
  if (detail) await openDetail(detail)
}
```

修复后请同时：
1. 补一个真实复现的端到端验证（点击"编辑" → KeyWorkView → 看到对应记录详情/编辑面板）
2. 在 review 文件"修复记录"中贴修改后的代码片段（而非文字说明）
3. 再 squash 一个 fix commit 到 tc-3 分支

---

## 修复确认（R3）

### P0-1 — KeyWorkView 二次解包 ✅ 已真修复

```js
const res = await kwApi.findKeyWorkByChild(type, childId)
const kwId = res?.key_work_id  // 拦截器已解包，res 直接为 data.data
if (kwId) {
  const detail = await kwApi.getKeyWork(kwId)
  if (detail) await openDetail(detail)
}
```

- **提交**：`3e0288c`（基于 `60e05d8` 之上的 fix commit）
- 修复后 vite build 零错误
- 端到端验证路径：用户点击来源记录的
