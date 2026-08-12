# Task: sup-2 - PMWB 后端督办邮件服务

## 基本信息
- **分支**: feature/sup-2-supervise-service
- **级别**: S2
- **依赖**: sup-1

## 目标
新增 PMWB 督办邮件服务，封装"按场景选模版 + 注入工单完整信息 + 调统一邮件中心发送"，供会议行动项与各工单模块复用。发送失败降级（不 500）。

## 改动范围
| 类型 | 文件路径 | 说明 |
|------|----------|------|
| 新增 | backend/services/supervise.py | supervise_ticket(scene, ticket, recipients) / supervise_action(...) |
| 新增 | backend/routers/supervise.py | POST /supervise/ticket、/supervise/action |
| 修改 | backend/main.py（或 api 汇聚处） | 注册 supervise 路由 |

## 技术要求
- 入参 `scene ∈ {sync, urge}`；自动选模版 id（`tpl_ticket_sync` / `tpl_ticket_urge`）。
- 注入字段：工单标题/编号/类型/负责人/截止/描述/状态/来源；会议行动项注入会议标题+内容+负责人+截止。
- 调 `EmailCenterClient.send_email(template_id=..., template_data=..., raise_on_error=False)`，判 `result["ok"]`，失败记日志+返回失败态，不抛异常。
- 收件人邮箱解析：优先传邮箱，否则用 `resolve_contact_emails(姓名)` 解析。
- 正文必须包含工单完整信息（满足需求2"邮件正文都要包含工单完整的信息"）。

## 完成标准 (DoD)
- [ ] 督办接口可用，pytest 覆盖 sync/urge + 失败降级
- [ ] 邮件正文含工单完整信息
- [ ] 不直连 SMTP

## 禁止项清单
- 禁止各模块各自拼邮件正文，统一走 sup_service。
- 不改邮件中心仓库代码（仅调用其 API）。
