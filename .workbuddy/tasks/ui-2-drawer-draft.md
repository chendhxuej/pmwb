# Task: ui-2 - 抽屉表单草稿防丢失

## 基本信息
- **分支**: feature/ui-2-drawer-draft
- **级别**: S2
- **依赖**: 无

## 目标
抽屉表单在误关（点遮罩/ESC/关闭按钮）时不丢失已填内容：草稿自动持久化（localStorage，按 路由+抽屉标识 维度），重开抽屉自动恢复；存在未保存修改时关闭前二次确认。至少保证信息不丢失。

## 改动范围
| 类型 | 文件路径 | 说明 |
|------|----------|------|
| 新增 | frontend/src/composables/useDrawerDraft.js | 草稿存取 composable |
| 修改 | 关键抽屉（会议详情、工单编辑、督办弹窗等） | 接入草稿恢复 + before-close 确认 |

## 技术要求
- `useDrawerDraft(key, reactiveForm)`：监听变化写 localStorage；open 时回填；close 时若 dirty 弹 `ElMessageBox.confirm`。
- key 形如 `${route.name}:${drawerId}` 防串台。
- 提交成功后清草稿。
- 不破坏现有表单校验逻辑，只加草稿层。

## 完成标准 (DoD)
- [ ] 误关会议/工单抽屉后重开，已填内容恢复
- [ ] 有未保存修改关闭时弹确认
- [ ] build + 冒烟通过

## 禁止项清单
- 不改变现有表单校验逻辑；只加草稿层。
