## 修复回复

### P0-1 — todo 深链断裂

- **根因**：todo 的 source_url 原为 /dashboard?id={r.id}，但 Dashboard 路由（HomeView）不处理 ?id= 参数
- **修复**：source_url 改为 /todo?id={r.id}，同时在 router 中注册了 /todo 路由 → TodoView（b0406b5/tc-1, 60e05d8/tc-3）
- **提交**：5b9d0b7 (tc-1: source_url 变更 + 测试断言修正), 60e05d8 (tc-3: /todo 路由注册)

## 修复状态

| 问题 | 严重度 | 状态 | 分支 | 提交 |
|:-----|:-------|:-----|:-----|:-----|
| P0-1 todo 深链断裂 | P0 | ✅ 已修复 | feature/tc-1-source-url-deeplink + feature/tc-3-module-deeplink | 5b9d0b7 / 60e05d8 |
