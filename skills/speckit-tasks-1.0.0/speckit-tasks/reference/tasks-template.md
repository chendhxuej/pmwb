---

description: "功能实现任务清单模板"
---

# 任务：[FEATURE NAME]

**输入**: 设计文档来自 `/specs/[###-feature-name]/`
**前置文档**: plan.md（必需）、spec.md（用户故事必需）、research.md、data-model.md、contracts/

**测试要求**: 以下示例包含测试任务。若项目宪章要求测试优先，则必须先写测试（Red），再写实现（Green）。

**组织方式**: 任务按用户故事分组，以支持独立实现与独立测试。

## 格式：`[ID] [P?] [Story] Description`

- **[P]**：可并行执行
- **[Story]**：所属用户故事
- 描述中应带准确文件路径

## 路径约定

- **单体项目**：`src/`、`tests/`
- **Web 应用**：`backend/src/`、`frontend/src/`
- **移动端**：`api/src/`、`ios/src/` 或 `android/src/`

## Phase 1: Setup

**目的**: 项目初始化

- [ ] T001 创建项目结构
- [ ] T002 初始化依赖
- [ ] T003 [P] 配置代码质量工具

## Phase 2: Foundational

**目的**: 阻塞性公共前置任务

- [ ] T004 建立基础设施
- [ ] T005 [P] 实现公共能力

## Phase 3+: 用户故事阶段

- [ ] T010 [P] [US1] 添加测试
- [ ] T011 [US1] 实现功能

## Final Phase: Polish

- [ ] TXXX 更新文档
- [ ] TXXX 清理代码
- [ ] TXXX 验证整体流程
