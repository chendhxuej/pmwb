# AGENTS.md - Agent Instructions

这是你的工作区，请按工作区方式行动。

## Every Session

每次会话开始前，先阅读 SOUL.md 和 USER.md，确保明确自身职责和任务上下文。

## Safety

- 永远不要泄露私人数据。
- 未经询问，请勿执行任何破坏性命令。
- 如有不确定之处，务必先询问确认。
- **邮件发送红线（最高优先级）**：AI 不得以任何理由（含"功能验证""测试"）用 curl/脚本向真实收件人发邮件。所有邮件发送自测一律走 dry_run（`dispatch_email` 默认 `MAIL_DRY_RUN=True`，不带 `confirm_send` 即只落库不真发）。真发只能由老大在页面显式点击触发（前端已固定带 `confirm_send=true`）。详见 `.workbuddy/memory/MEMORY.md`「邮件发送安全铁律」。

## External vs Internal

**可直接执行的内部操作：**
- 阅读 `spec.md`、宪章文档、模板和相关上下文文件。
- 识别未知项，并形成研究结论。
- 生成 `plan.md`、`research.md`、`data-model.md`、`contracts/` 目录内容。
- 检查方案是否违反宪章门禁。

**需要先征询的外部操作：**
- 任何离开本机或工作区边界的操作，例如访问外部系统或执行影响环境的命令，必须提前询问并获得许可。