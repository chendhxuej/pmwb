# Task: ui-1 - 右侧抽屉宽度统一 70%

## 基本信息
- **分支**: feature/ui-1-drawer-width
- **级别**: S3
- **依赖**: 无

## 目标
审计前端所有右侧 `el-drawer`，将宽度统一为 70%，避免各页面尺寸不一；抽离为共享常量或封装 `BaseDrawer` 组件。

## 改动范围
| 类型 | 文件路径 | 说明 |
|------|----------|------|
| 修改 | 各 view 中 `el-drawer` size 属性 | `680px`/`720px` 等改为 `"70%"` |
| 新增(可选) | frontend/src/components/BaseDrawer.vue | 统一封装（size 默认 70%） |

## 技术要求
- 仅改右侧抽屉（`direction="rtl"`）；居中 `el-dialog` 不在此范围（除非老大要求）。
- 用 `size="70%"`（Element Plus 支持百分比字符串）。
- Grep 全量确认所有 `el-drawer` 已覆盖。

## 完成标准 (DoD)
- [ ] 所有右侧抽屉宽度为 70%
- [ ] build 通过、冒烟无样式错乱

## 禁止项清单
- 不改业务逻辑，只调整抽屉宽度。
