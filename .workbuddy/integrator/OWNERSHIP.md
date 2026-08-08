# 文件/目录归属表（多 AI 管控）

> **编辑任何文件前先查本表。** 不在自己名下 → 不动，去 `INTEGRATION_QUEUE.md` 提协调申请，由集成者仲裁。
> 新增模块/文件请同步补充本表。违反归属导致互相覆盖即事故。

| 路径 / 模块 | 负责 AI | 分支 | 状态 | 备注 |
|---|---|---|---|---|
| **AI总结 / WorkReport**（`backend/routers/work_report.py`、`backend/schemas/work_report.py`、`backend/services/report_prompt.py`、`backend/services/report_collector.py`、`backend/services/report_llm.py`、`backend/services/work_report.py`、`frontend/src/api/workReport.js`、`frontend/src/views/WorkReportView.vue`、`backend/db/models.py` 的 `PmwbWorkReport` 类、`frontend/src/router/index.js` 的「AI总结」路由块） | **Vicky2号（集成者）** | `feature/ai-report`（待建） | 未入库，仅存磁盘 + 仓库外备份 | 曾被沙箱切分支搞丢，已重建；备份 `D:/项目/_wr_backup/work-report/` |
| **运营监控·监督/工单（sup-3）**（`supervise.js`、`SuperviseDialog.vue`、`TicketView.vue`、`WorkOrderView.vue` 等） | 开发者 AI（晓伴等） | `feature/sup-3-supervise-ui` | 开发中 | 勿动 |
| 已合入 main 的既有模块（mc/tc/ma/umc/db/kc 等） | 见 `.workbuddy/tasks/TASKS.md` | 已合入 `main` | 锁定 | 非领新任务不得改 |
| `.workbuddy/integrator/*`（本管控目录） | Vicky2号 | — | 管控 | 仅集成者维护 |

## 协调申请格式（写入 INTEGRATION_QUEUE.md 的「协调申请」区）
```
[协调] 申请改 <文件> ：原因 <…> ；申请人 <AI> ；期望归属 <…>
```
