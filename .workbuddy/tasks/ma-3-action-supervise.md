# Task: ma-3 - 会议行动项增强与督办接口

## 基本信息
- **分支**: feature/ma-3-action-supervise
- **级别**: S2
- **预估**: 后端 3 文件
- **依赖**: sup-2（督办邮件服务）

## 目标
在现有 `MeetingAction`（会议行动项）模型基础上，提供独立于会议详情的"行动项"查询与管理能力，并新增"发起督办"接口——调用 sup_service 给行动项负责人发送督办邮件（正文含行动项完整信息）。

## 改动范围
| 类型 | 文件路径 | 说明 |
|------|----------|------|
| 新增 | backend/routers/meeting_action.py | 行动项列表/筛选接口 + 发起督办接口 |
| 修改 | backend/services/meeting.py | 新增 list_actions(filter)、supervise_action(...) |
| 修改 | backend/schemas/meeting.py | 新增 MeetingActionQuery / MeetingActionSupervise 入参 |

## 技术要求
- 行动项列表支持按 `meeting_id / owner / status / due_before` 筛选，返回 `MeetingActionOut` 且附带所属会议标题。
- 督办接口：`POST /meetings/{mid}/actions/{aid}/supervise`，入参 `{scene: 'sync'|'urge', extra_msg?}`，内部调 `sup_service.send_action_supervise(...)`。
- 复用 `utils/dateflags.py` 的 `is_overdue` 判定催办必要性（urge 场景仅对临期/逾期项生效）。
- 时区 UTC+8；响应走 `success()` 解包（code===0 返回 data）。

## 完成标准 (DoD)
- [ ] 行动项独立查询接口可用（pytest 覆盖筛选分支）
- [ ] 督办接口发送成功，邮件正文含行动项完整信息
- [ ] 邮件中心不可用时降级不 500（raise_on_error=False）
- [ ] 无 alembic 模型变更（复用现有表）

## 禁止项清单
- 不改 `MeetingAction` 表结构（本次只加查询/督办）。
- 禁止直连 SMTP，必须走 sup_service → 统一邮件中心。
- 不动旧 `HomeView.vue`。
