# ma-1 后端：会议行动项完整返回 + synced_to_todo 标记

## 背景上下文
当前 `collect_meeting_action`（`backend/services/task_center.py:218`）有一句去重：`if r.related_todo_id: continue`（line 227-228），凡是被"同步为个人待办"的会议行动项，直接从"会议行动项"来源跳过，导致用户在任务中心"会议行动项"标签看不到它们（实际在"个人待办"）。需求：会议行动项标签展示全部行动项，已同步的标"已转待办"徽标（由前端 ma-2 展示）。

## 精确改动范围
文件：`backend/services/task_center.py` + `backend/schemas/task_center.py`
- 删除 `collect_meeting_action` 中 line 227-228 的 `if r.related_todo_id: continue`。
- 在 `TaskItem`（schema，`schemas/task_center.py:38`）新增字段 `synced_to_todo: bool = False`。
- 在 `collect_meeting_action` 每项填 `synced_to_todo=bool(r.related_todo_id)`。
- 不动 `collect_todo`、不动 `related_todo_id` 数据、不动其他来源。

## 可执行验收命令
- `pytest tests/test_task_center.py` 全绿（补断言：已同步的行动项出现在 meeting_action 来源且 `synced_to_todo=true`）。
- `curl .../task-center/tasks?source=meeting_action` 返回全部行动项（含已同步），字段含 `synced_to_todo`。
- 个人待办来源不受影响（仍含同步副本，符合预期）。

## 禁止项清单
- 不删除 `related_todo_id` 或改动同步逻辑（`meeting.py:sync_action_todo`）。
- 不改其他来源聚合。
- 不引入新表/迁移（仅 schema 加可选字段）。

## 起点指引
读 `task_center.py:218-251` 与 `schemas/task_center.py:38 TaskItem`。同步逻辑参考 `services/meeting.py:159`。
