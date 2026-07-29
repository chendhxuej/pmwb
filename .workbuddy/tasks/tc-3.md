# tc-3 交付记录

- **状态**：🟡待审查 (晓伴)
- **分支**：`feature/tc-3-module-deeplink`
- **提交**：`78df319`
- **前置依赖**：tc-1（source_url 深链）、tc-2（编辑按钮）

## 变更内容

### 前端 5 模块深链定位

| 模块 | 深链参数 | 行为 |
|:-----|:---------|:-----|
| TodoView | `?id={id}` | 定位待办 → 打开编辑对话框 |
| WorkOrderView | `?issueId={id}` | 定位运营问题 → 打开详情 → 进入编辑态 |
| RequirementDeliveryView | `?ticket={ticket_no}` | 定位研发工单 → 打开编辑对话框 |
| RequirementDeliveryView | `?req={req_id}&sa={sa_name}` | 定位需求评估 → 打开编辑对话框 |
| MeetingView | `?actionId={id}` | 遍历已含 actions 的列表 → 定位会议 → 打开详情 |
| KeyWorkView | `?id=task-{id}` | 通过 by-child 端点定位 → 打开详情 |
| KeyWorkView | `?id=milestone-{id}` | 通过 by-child 端点定位 → 打开详情 |

### 后端新增（最小化缺口填补）

- `services/keywork.py`: `find_by_member_task` / `find_by_milestone` 静态方法
- `routers/keywork.py`: `GET /key-works/by-child?type=task|milestone&id={id}` 端点
- `api/keywork.js`: `findKeyWorkByChild(type, id)` 前端 API 函数

### 重要技术决策

- **MeetingView actionId 定位**：利用列表 API 已 `joinedload(actions)` 的特性，直接在已加载的数据中遍历查找，无需额外 API
- **KeyWorkView 需要后端支持**：列表 API 明确排除了 children（减重），无法纯前端定位，因此新增轻量级 by-child 端点

### 自测

- 前端 vite build ✅
- 后端 pytest（dashboard 5 passed）✅
