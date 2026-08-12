# 审查反馈: mc-2 第 1 轮

- **审查者**: Vicky2号 (集成者)
- **日期**: 2026-07-28
- **审查结��**: 🔴退回修改

---

## 问题清单

### 🔴 P0 - 必须修复（阻塞合入）

| # | 文件 | 问题描述 | 期望修复 | 状态 |
|---|------|----------|----------|------|
| 1 | backend/tests/test_basic_data.py | 分支中混入了后端的测试文件修改（uuid 唯一名称隔离）— 与 mc-2 前端任务无关 | 恢复为 origin/main 版本（`git checkout origin/main -- backend/tests/test_basic_data.py`） | ✅ |
| 2 | services/master/.env | 混入了 Master Service 的环境配置修改 — 与 mc-2 无关 | 恢复为 origin/main 版本 | ✅ |
| 3 | services/master/app/services/basic_data.py | 混入了人员中台业务逻辑修改 — 与 mc-2 无关 | 恢复为 origin/main 版本 | ✅ |

### 🟡 P1 - 建议修复（合入前应处理）

无。

### 🟢 P2 - 可选优化（可合入后改进）

| # | 文件 | 建议 |
|---|------|------|
| 1 | frontend/src/views/mail/MailCenterLayout.vue | MailLogsPlaceholder 可直接合并到 MailCenterLayout 中作为内联组件，减少文件碎片 |

---

## 改进建议（面向开发者）

### 本次发现的模式问题

**分支泄漏（Branch Leak）**：分支上提交了与任务无关的文件。这通常是因为开发时在主分支或别的分支上做过微调，切到任务分支后 `git add .` 带进来了。

**防止方法**：
1. 提交前用 `git diff --name-only main..HEAD` 确认所有改动文件都在 Task Spec 的「改动范围」内
2. 不在 feature 分支上做任务范围外的改动
3. 如果确实需要改其他文件，先切回 main 开新分支处理

### 引用的项目约定
- `.workbuddy/memory/MEMORY.md` → "协同开发规范" → 分支铁律
- `docs/COLLABORATIVE_DEV_WORKFLOW.md` → 第二节 → 分支策略

---

## 开发者回复区

> **晓伴**：请在此区域填写修复说明。

<!-- feedback:start -->

### 修复记录

| 问题 # | 修复说明 | 提交 SHA |
|--------|----------|----------|
| P0-1 | 已恢复 test_basic_data.py 为 origin/main 版本 | — |
| P0-2 | 已恢复 master/.env 为 origin/main 版本 | — |
| P0-3 | 已恢复 basic_data.py 为 origin/main 版本 | — |

### 开发者备注
P0 文件由集成者协助恢复并直接合入。今后提分支前会先 `git diff main..HEAD` 自查。

<!-- feedback:end -->

---

## 审查历史

| 轮次 | 日期 | 结论 | 备注 |
|------|------|------|------|
| R1 | 2026-07-28 | 🔴退回修改 | 3 个 P0 分支泄漏 |
| 最终 | 2026-07-28 | ✅已合入 | Vicky2号协助移除污染文件后直接合入 main (a5aac42→fd8afca) |
