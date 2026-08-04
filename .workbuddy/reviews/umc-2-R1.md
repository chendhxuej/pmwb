## 修复回复

### P1-1 — 中台宕机时抛 500

- **根因**：`GET /contacts` 的 catch 直接 `next(err)`，`MasterServiceError` 被 Express 错误中间件统一转换为 500
- **修复**：在 catch 中增加 `err instanceof MasterServiceError` 分支，返回 HTTP 502 + `{ error: ..., items: [] }`，前端收到非 200 状态码时展示"通讯录暂不可用"提示
- **提交**：`40a2690`

### P2-1 — groupId 过滤丢失

- **根因**：contacts 数据从中台读取后无分组概念，groupId 参数不生效
- **修复**：GET handler 中增加废弃警告日志（console.warn），groupId 参数仍保留在 schema 中避免破坏已有调用方，但实际过滤逻辑移除
- **提交**：`40a2690`

## 修复状态

| 问题 | 严重度 | 状态 | 提交 |
|:-----|:-------|:-----|:-----|
| P1-1 中台宕机 500 抛错 | P1 | ✅ 已修复（502 降级） | 40a2690 |
| P2-1 groupId 过滤丢失 | P2 | ✅ 已修复（废弃警告） | 40a2690 |
