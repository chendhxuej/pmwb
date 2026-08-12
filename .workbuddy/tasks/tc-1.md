# tc-1 后端：6 类采集器 source_url 改为深链（含 source_id），修正待办路由

## 背景上下文
任务中心（`TaskCenterView.vue`）操作列将新增"编辑"按钮，跳转来源模块并定位到具体工单。前端 `gotoSource(task)` 已支持按 `task.source_url` 跳转（`TaskCenterView.vue:377-380`），但当前 `backend/services/task_center.py` 各采集器填的 `source_url` 只到模块根路径（如 `/meeting`），且 `todo` 误指向 `/dashboard`（首页），无法定位具体工单。本任务把 `source_url` 改为带定位参数的深链。

## 精确改动范围
文件：`backend/services/task_center.py` 的 6 个 collector（line 118-408）：
- `collect_todo` → `source_url=f"/todo?id={r.id}"`（⚠️ 先确认 `TodoView` 路由名与 query 约定；若无独立 `/todo` 路由，需与 tc-3 商定改用现有待办维护页路由，禁止直接沿用错误的 `/dashboard`）
- `collect_operation_issue` → `source_url=f"/operation?issueId={r.id}"`（确认 `WorkOrderView` 支持的 query 参数名）
- `collect_dev_ticket` → `source_url=f"/requirement-delivery?ticket={r.ticket_no}"`
- `collect_meeting_action` → `source_url=f"/meeting?actionId={r.id}"`
- `collect_key_work` → `source_url=f"/key-works?id={r.id}"`（member_task 与 milestone 的 id 需区分，建议 `?id=task-{id}` / `?id=milestone-{id}`，与 `source_id` 一致）
- `collect_requirement_urge` → `source_url=f"/requirement-delivery?req={r.req_id}&sa={owner}"`

注意：
- 先 Grep `frontend/src/router/index.js` 与各模块 View 确认路由路径与 query 参数命名，避免 URL 拼错跳转落空。
- 若需新增字段（如 `edit_url`），同步改 `backend/schemas/task_center.py` 的 `TaskItem` 并补 migration（仅当加列）。

## 可执行验收命令
- `cd backend && python -m pytest tests/test_task_center.py -q` 全绿（如缺该测试文件需补：断言 6 类 `source_url` 含定位参数且 `todo` 不再指向 `/dashboard`）。
- 后端起服务：`curl localhost:8000/api/v1/task-center/tasks?source=meeting_action` 返回项 `source_url` 形如 `/meeting?actionId=数字`。
- `vite build` 不受影响（本任务纯后端）。

## 禁止项清单
- 不改聚合/去重逻辑（那是 ma-1 的事）。
- 不改前端、不改各来源表结构。
- 不引入新依赖。

## 起点指引
1. 读 `backend/services/task_center.py` 第 118-408 行（6 个 collector）。
2. Grep `frontend/src/router/index.js` 确认路由：`/operation`、`/requirement-delivery`、`/meeting`、`/key-works`、`/todo`(待确认)。
3. 改 6 处 `source_url`，补 pytest。
