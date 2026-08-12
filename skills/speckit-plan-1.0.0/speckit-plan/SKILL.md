---
name: speckit-plan
description: 基于功能规格生成技术实现计划。
author: zhuhaopeng
---

# Speckit 规划技能

## 用户输入

```text
$ARGUMENTS
```

如果用户提供了输入，你**必须**在执行前纳入考虑。

## 执行前检查

**检查扩展钩子（规划之前）**：
- 检查项目根目录下是否存在 `.specify/extensions.yml`
- 若存在，读取 `hooks.before_plan`
- 若 YAML 无法解析或格式非法，则静默跳过并继续
- 过滤掉 `enabled: false` 的钩子；未设置 `enabled` 的默认启用
- 对每个剩余钩子，**不要**计算 `condition`：
  - 无 `condition` 或为空时，视为可执行
  - 存在非空 `condition` 时，跳过，交给 HookExecutor 处理
- 对可执行钩子，根据 `optional` 输出：
  - **可选钩子**（`optional: true`）：
    ```
    ## 扩展钩子

    **可选前置钩子**: {extension}
    Command: `/{command}`
    说明: {description}

    Prompt: {prompt}
    To execute: `/{command}`
    ```
  - **强制钩子**（`optional: false`）：
    ```
    ## Extension Hooks

    **自动前置钩子**: {extension}
    Executing: `/{command}`
    EXECUTE_COMMAND: {command}

    Wait for the result of the hook command before proceeding to the Outline.
    ```
- 若没有钩子或 `.specify/extensions.yml` 不存在，则静默跳过

## 执行概要

1. **初始化**：在仓库根目录运行 `.specify/scripts/powershell/setup-plan.ps1 -Json`，并从 JSON 中解析 `FEATURE_SPEC`、`IMPL_PLAN`、`SPECS_DIR`、`BRANCH`。如果参数里有单引号（如 `I'm Groot`），请使用正确转义。

2. **加载上下文**：读取 `FEATURE_SPEC` 和 `.specify/memory/constitution.md`。将 `reference/plan-template.md` 作为规划主模板，将 `reference/agent-file-template.md` 作为 agent 上下文输出结构参考。

3. **执行规划流程**：按照 `IMPL_PLAN` 模板结构完成以下内容：
   - 填写技术上下文（未知项标记为 `NEEDS CLARIFICATION`）
   - 依据宪章填写 Constitution Check
   - 评估各项门禁（若存在未合理说明的违反项则报错）
   - Phase 0：生成 `research.md`（解决所有 `NEEDS CLARIFICATION`）
   - Phase 1：生成 `data-model.md`、`contracts/`、`quickstart.md`
   - Phase 1：运行 agent 脚本更新 agent context
   - 在设计完成后重新检查 Constitution Check

4. **停止并汇报**：该命令在完成 Phase 2 规划后结束。向用户汇报分支名、`IMPL_PLAN` 路径以及已生成的产物。

5. **检查扩展钩子**：汇报后检查 `.specify/extensions.yml`：
   - 若存在，读取 `hooks.after_plan`
   - 若 YAML 无法解析或格式非法，则静默跳过
   - 过滤掉 `enabled: false` 的钩子；默认启用未显式设置的项
   - 对每个剩余钩子，**不要**计算 `condition`
   - 对可执行钩子，根据 `optional` 输出对应说明
   - 若没有钩子或配置文件不存在，则静默跳过

## 阶段说明

### Phase 0：轮廓与调研

1. 从上面的技术上下文中提取未知项：
   - 每个 `NEEDS CLARIFICATION` → 形成一个调研任务
   - 每个依赖项 → 形成最佳实践调研任务
   - 每个集成点 → 形成模式调研任务

2. 生成并分发研究任务：

   ```text
   For each unknown in Technical Context:
     Task: "Research {unknown} for {feature context}"
   For each technology choice:
     Task: "Find best practices for {tech} in {domain}"
   ```

3. 将研究结论汇总到 `research.md`，格式如下：
   - Decision: [最终选择]
   - Rationale: [选择原因]
   - Alternatives considered: [评估过的备选方案]

**输出**：一份解决全部 `NEEDS CLARIFICATION` 的 `research.md`

### Phase 1：设计与契约

**前提条件**：`research.md` 已完成

1. 从功能 spec 中提取实体，写入 `data-model.md`：
   - 实体名称、字段、关系
   - 来源于需求的校验规则
   - 若适用，补充状态流转

2. 定义接口契约（如果项目存在对外接口），输出到 `/contracts/`：
   - 识别项目对用户或外部系统暴露的接口
   - 以适合项目类型的格式记录契约
   - 示例：库的公开 API、CLI 的命令模式、Web 服务的端点、解析器语法、应用的 UI 契约等
   - 若项目完全是内部型（构建脚本、一次性工具等），则可跳过

3. **更新 agent context**：
   - 运行 `.specify/scripts/powershell/update-agent-context.ps1 -AgentType agy`
   - 这些脚本会自动检测当前使用的 AI agent
   - 更新相应的 agent 专用上下文文件
   - 仅添加当前计划中新出现的技术
   - 保留标记区间内的人工补充内容

**输出**：`data-model.md`、`/contracts/*`、`quickstart.md`、agent 专用上下文文件

## 关键规则

- 使用绝对路径
- 若门禁失败或仍有未解决的澄清项，则直接报错

