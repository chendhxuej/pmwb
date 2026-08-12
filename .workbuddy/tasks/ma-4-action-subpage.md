# Task: ma-4 - 会议行动项独立子模块（前端）

## 基本信息
- **分支**: feature/ma-4-action-subpage
- **级别**: S2
- **预估**: 前端 2-3 文件
- **依赖**: ma-3

## 目标
在"会议日程"模块新增"会议行动项"子页面，聚合展示所有会议产生的行动项，支持按会议/负责人/状态筛选、内联编辑、一键发起督办。

## 改动范围
| 类型 | 文件路径 | 说明 |
|------|----------|------|
| 新增 | frontend/src/views/MeetingActionsView.vue | 行动项列表+筛选+编辑抽屉+督办入口 |
| 修改 | frontend/src/router/index.js | 新增 `/meeting-actions` 路由（侧栏"会议行动项"入口） |
| 修改 | frontend/src/api/meeting.js | 新增 listActions / superviseAction 接口 |

## 技术要求
- 列表列：行动项内容、所属会议、负责人（StaffSelect）、截止日期、状态（可切换）、操作（编辑/督办）。
- 编辑复用现有 `MeetingActionOut` 字段；状态切换即调更新接口落库。
- 督办：弹窗选场景(同步/催办)+补充留言 → 调 superviseAction。
- 抽屉宽度 70%（接入 ui-1 规范）；表单草稿防丢失（接入 ui-2）。
- 统一用 `request.js` baseURL `/api/v1`，接口路径相对。

## 完成标准 (DoD)
- [ ] 页面可列出全部行动项并筛选
- [ ] 状态切换/编辑落库
- [ ] 督办按钮可发送且收到含完整信息的邮件
- [ ] vitest 通过、npm run build 干净、无头冒烟无白屏

## 禁止项清单
- 不改动旧 `HomeView`；新页面走新路由。
- 不直连邮件，走 sup 接口。
