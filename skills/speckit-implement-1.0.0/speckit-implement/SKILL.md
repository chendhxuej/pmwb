---
name: speckit-implement
description: 按任务拆解执行全部实现工作并完成功能开发。
author: zhuhaopeng
---

# Speckit 实现技能

## 用户输入

```text
$ARGUMENTS
```

如果用户提供了输入，你**必须**在执行前纳入考虑。

## 执行前检查

**检查扩展钩子（实现之前）**：
- 检查 `.specify/extensions.yml` 是否存在
- 若存在，读取 `hooks.before_implement`
- 若 YAML 无法解析，则静默跳过
- 过滤 `enabled: false`，其余默认启用
- 不要解释 `condition`
- 对每个可执行钩子，根据 `optional` 输出说明
- 若无配置则静默跳过

## 执行概要

1. 在仓库根目录运行 `.specify/scripts/powershell/check-prerequisites.ps1 -Json -RequireTasks -IncludeTasks`，并解析 `FEATURE_DIR` 与 `AVAILABLE_DOCS`。所有路径必须使用绝对路径。

2. **检查 checklist 状态**（若 `FEATURE_DIR/checklists/` 存在）：
   - 扫描 `checklists/` 目录下所有清单文件
   - 对每个清单统计：
     - 总项数：匹配 `- [ ]`、`- [X]` 或 `- [x]` 的行
     - 已完成项：匹配 `- [X]` 或 `- [x]` 的行
     - 未完成项：匹配 `- [ ]` 的行
   - 生成状态表
   - 计算总体状态：
     - **PASS**：所有清单都没有未完成项
     - **FAIL**：一个或多个清单仍有未完成项
   - **若存在未完成项**：
     - 展示状态表
     - **停止** 并询问：`Some checklists are incomplete. Do you want to proceed with implementation anyway? (yes/no)`
     - 等待用户回答后再继续
   - **若全部完成**：
     - 展示全部通过的状态表
     - 自动进入下一步

3. 加载并分析实现上下文：
   - **必须**：读取 `tasks.md`，获取完整任务列表与执行顺序
   - **必须**：读取 `plan.md`，获取技术栈、架构与文件结构
   - **如果存在**：读取 `data-model.md`、`contracts/`、`research.md`、`quickstart.md`
   - 使用 `reference/tasks-template.md` 与 `reference/checklist-template.md` 作为本地结构参考，校验输入产物是否符合预期

4. **项目初始化校验**：
   - **必须**：根据项目实际情况创建或校验忽略文件
   - 检查是否为 git 仓库，必要时创建/校验 `.gitignore`
   - 若存在 Dockerfile 或计划中提到 Docker，则创建/校验 `.dockerignore`
   - 若存在 ESLint / Prettier / npm / Terraform / Helm 等配置，则创建或补齐相应 ignore 文件
   - 若忽略文件已存在，仅补充缺失的关键模式，不做无关改动

5. 解析 `tasks.md` 结构并提取：
   - 各任务阶段：初始化、测试、核心实现、集成、收尾
   - 任务依赖：串行与并行规则
   - 任务详情：ID、描述、文件路径、`[P]` 标记
   - 执行流程：顺序与依赖要求

6. 按任务计划执行实现：
   - **按阶段推进**：完成一个阶段后再进入下一个阶段
   - **遵守依赖**：串行任务按顺序执行，可并行任务可以同时推进
   - **遵循 TDD**：测试任务优先于对应实现任务
   - **按文件协调**：涉及同一文件的任务必须串行执行
   - **阶段校验**：每完成一个阶段都进行验收确认

7. 实现执行规则：
   - **先做 Setup**：完成项目结构、依赖、配置等初始化工作
   - **先写测试再写代码**：适用于契约、实体与集成场景测试
   - **核心开发**：实现模型、服务、CLI 命令、端点等
   - **集成工作**：数据库连接、中间件、日志、外部服务
   - **收尾与验证**：单测、性能优化、文档完善

8. 进度跟踪与错误处理：
   - 每完成一项任务后报告进度
   - 若非并行任务失败，则停止执行
   - 对并行任务，继续成功项，并报告失败项
   - 提供带上下文的清晰报错信息
   - 若实现无法继续，给出下一步建议
   - **重要**：任务完成后，务必把 `tasks.md` 中对应的 `[ ]` 标记为 `[X]`

9. 完成校验：
   - 确认所有必需任务均已完成
   - 确认最终实现符合原始 specification
   - 验证测试通过，且覆盖率达到要求
   - 确认实现符合技术计划
   - 汇报最终状态与完成摘要

说明：该命令假设 `tasks.md` 已完整存在。若任务缺失或不完整，应提示先运行 `/speckit.tasks` 重新生成任务清单。

10. **检查扩展钩子**：完成校验后，检查 `.specify/extensions.yml` 中的 `hooks.after_implement`，处理方式与前置钩子一致。

