# umc-1 交付记录

- **状态**：🟡待审查 (晓伴)
- **仓库**：`D:\项目\统一邮件中心\server`（tongyi_email）
- **分支**：`feature/umc-1-master-service`
- **提交**：`590b7bb`（tongyi_email 仓库）

## 变更内容

### 新增文件

| 文件 | 用途 |
|:-----|:------|
| `src/services/masterService.ts` | 人员中台出站 HTTP 客户端 |
| `src/services/masterService.test.ts` | 集成测试（11 用例） |

### 核心接口

| 函数 | 说明 |
|:-----|:------|
| `fetchStaffOptions(forceRefresh?)` | 获取按组织分组的人员列表，含 30s 内存缓存 |
| `healthCheck()` | 探测中台 `/api/v1/health` 是否可达 |
| `clearCache()` | 清空缓存（测试/手动刷新） |
| `MasterServiceError` | 可捕获的错误类型 |

### 技术实现

- **原生 fetch**（Node 22+），不引入 axios 等额外依赖
- **5s 超时**：`AbortController` 实现
- **错误降级**：中台不可用/超时/异常时抛出 `MasterServiceError`，调用方捕获后降级
- **30s TTL 内存缓存**：缓存中台组织人员数据，减少重复请求
- **TypeScript**：完整类型定义（`MasterStaffOrgGroup` / `MasterStaffOption`）

### 依赖的中台接口

`GET http://localhost:8001/api/v1/basic-data/staff-options`

返回结构：
```json
{
  "code": 0,
  "message": "success",
  "data": [
    {
      "org_id": 32,
      "org_name": "BOSS",
      "options": [
        { "value": "姓名", "label": "姓名", "email": "xxx@xx.com", "role_hint": "SA" }
      ]
    }
  ]
}
```

### 自测

- `npx tsc --noEmit` — 零类型错误 ✅
- `npx tsx src/services/masterService.test.ts` — 11/11 通过 ✅
