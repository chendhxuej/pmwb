# Task: sup-3 - 各工单模块督办按钮（前端）

## 基本信息
- **分支**: feature/sup-3-supervise-ui
- **级别**: S2
- **依赖**: sup-2

## 目标
在开发工单 / 运营问题 / 需求催办等工单类模块的列表与详情新增"邮件督办"按钮，弹窗选场景(信息同步/催办)+补充留言+收件人，调 sup-2 发送；正文自动携带该工单完整信息。

## 改动范围
| 类型 | 文件路径 | 说明 |
|------|----------|------|
| 新增 | frontend/src/components/SuperviseDialog.vue | 通用督办弹窗（场景选择+收件人+留言） |
| 修改 | frontend/src/views/WorkOrderView.vue | 列表/详情加"邮件督办" |
| 修改 | frontend/src/views/RequirementDeliveryView.vue（及运营问题页） | 加督办入口 |
| 新增 | frontend/src/api/supervise.js | 封装督办接口 |

## 技术要求
- 督办弹窗复用 `StaffSelect` 选收件人；场景 radio（同步/催办）。
- 发送后 `ElMessage` 反馈；失败提示但不崩溃。
- 抽屉/弹窗宽度 70%（ui-1）；表单草稿防丢失（ui-2）。

## 完成标准 (DoD)
- [ ] 三类工单均可发起督办并收到含完整信息的邮件
- [ ] vitest + build 通过 + 冒烟无白屏

## 禁止项清单
- 不直连邮件；走 `/api/v1/supervise/*`。
