# PMWB 项目长期记忆

## 项目状态
- 技术栈：FastAPI + Vue3 + Element Plus + MySQL + Obsidian 联动；GitHub chendhxuej/pmwb (main)。服务拓扑：主后端 8000 / 人员中台 8001(独立 FastAPI+alembic) / 前端 5173 / MySQL 3306 / 统一邮件中心 3210(外部)。
- 前端 IA（2026-08-04 核对）：首页看板 → 任务中心 → 需求与交付 → 运营监控 → 会议日程 → 个人待办 → 重点工作 → 人员中台 → 知识中心 → 邮件中心。
- 业务知识联动（2026-08-05）：`pmwb_business_domain` 12 条种子；`domain_code` 已铺到业务表 + `pmwb_knowledge_item`；前端统一用 `BusinessDomainSelect.vue` 选领域、`RelatedKnowledgePanel.vue` 展示同领域知识。知识中心批次十二 kc-2（kc-2-1~7）已全部合入 main：关联基础设施 + 主笔记体系(note_type列/ensure主笔记保活/子笔记摘要聚合/树形) + 需求沉淀(回链主笔记+场景规则子笔记+操作手册归档) + 运营结构化(4字段+场景规则沉淀) + 会议关联(force覆盖/删除纪要/多选关联)。
- 测试基线：pytest 123 passed / 5 failed（5 失败均为 Master 8001 沙箱故障 + dashboard 日期等既有环境问题，与功能改动无关）；vitest 7/7；vite build 干净。

## 启动方案（看门狗常驻保活）
- `C:\pmwb-scripts\pmwb-keeper.py`(镜像 `scripts/`)每 15s 查 3306/8000/5173/3210/8001，DOWN 用已验证控制台命令 DETACHED 拉起；后端/Master 等 3306 就绪才起。桌面 `启动PMWB.bat`(常驻)、`重启PMWB.bat`(按端口终止+重启)。
- **开机自启铁律**：`pmwb-autostart.vbs` 必须 `cmd /c "<python.exe>" "<keeper.py>"`。**绝不能用 `pythonw`/`Run/Start-Process` 隐藏窗口拉 python.exe**——`mysqld --console` 静默失败、数据库起不来。
- **⚠️ 陈旧 PMWB 服务占位坑（高复发）**：曾 3 个 PMWB-* NSSM 服务 + PMWB-MySQL 计划任务（已 `scripts/uninstall-windows-services.bat` 右键管理员永久删除）。若「改了后端代码不生效(404)」先查是否残留旧服务占 8000；沙箱令牌被 UAC 过滤无法在沙箱内 taskkill 重启，需本机管理员。
- **⚠️ Ghost Port 坑**：Python 进程 Kill 后 TCP LISTENING socket 可能残留（netstat 有 PID 但 process 不存在），看门狗 `port_up()` 误判→不拉新后端→过期代码。修复：`Get-Process python | Stop-Process -Force` 清 Python + 重启 keeper。
- 服务化脚本(`install-windows-services.ps1` 等)已弃用。

## 关键技术约定（高频坑）
- API：request.js baseURL='/api/v1'，api 文件用相对路径（如 '/requirements'）；拦截器 code===0 返回 data.data，禁止二次解包。
- `success()` 用 `message=`(非 `msg=`)，否则 TypeError→500。
- 时区：中国 UTC+8；统计用 `datetime.now(timezone(timedelta(hours=8)))`，库表 UTC 存、展示 ±8h，勿 utcnow 当本地今天。
- 前端日期空值传 `""` → Pydantic `Optional[date]` 422；Update schema 加 `@field_validator(mode="before")` 把 `""`/`None` 转 None。
- **图标引用坑**：数组字面量 `icon: Xxx` 立即求值，Xxx 必须已 import 且真实存在；漏 import/拼错→白屏，Rollup 不报错，**浏览器无头冒烟是必过项**。
- **菜单 hidden 坑**：`MainLayout.vue` 的 `menuItems` 必须 `.filter(c=>!c.meta?.hidden)` 才真正隐藏。
- **⚠️ SQLite/MySQL 方言坑**：测试用 SQLite 内存库，`cast(col, Date)` 在 SQLite 走 numeric affinity 失效（MySQL 正常）。日期区间统计一律改用 naive datetime 上下界比较（`>= day_start, < day_end`）。
- 沙箱删守卫：Obsidian vault 路径 os.remove/rmtree 被沙箱拦截(409)，真实环境正常，勿改业务逻辑绕过。
- **抽屉草稿约定**：`frontend/src/composables/useDrawerDraft.js` 统一草稿持久化（localStorage，storageKey 含记录 ID）；新增右抽屉/录入弹窗优先复用。

## 架构整改约定
- **催办/逾期判据单一来源**：`backend/utils/dateflags.py`（`is_overdue`/`is_due_soon`/`flag_due_date`/`relative_status`）；task_center/requirement/reminder 禁止各自实现。
- **邮件发送降级契约**：`EmailCenterClient.send_email(...)` 返回 `{"ok","data"?,"error"?}`；业务侧 `raise_on_error=False` 判 `result["ok"]`，失败只落 `send_status=failed`+记 `error_msg`，不得抛异常中断。超时 30s→10s。
- **配置强制环境变量**：`SECRET_KEY`/`DB_PASSWORD` 必填从 `.env` 读，缺失即报错；`DEBUG` 默认 False。
- 改 SQLAlchemy 模型(增/改列)后必须先 `alembic upgrade head` 再起后端（否则 1054 Unknown column→前端500）。
- **⚠️ Alembic 修订号冲突坑**：新建迁移前先 `alembic heads` 查现有号；`20260804000001` 已被 `add_minutes_required` 占用。新迁移取 heads 最大号 +1，`down_revision` 指向实际 head。
- **会议邮件收件人兼容「姓名/邮箱」**：`services/meeting.py send_mail` 的 `to`/`cc` 支持「中文姓名或邮箱」混合，非邮箱经 `MasterServiceClient.resolve_staff_emails` 解析。

## 协同开发规范（铁律）
- **禁止在 main 直开发**：所有改动走 feature 分支 → Vicky2号审查合版。角色：Vicky2号=集成者（拆任务/建分支/审查/合版/推送）；其他 AI=开发者；老大=决策者。
- 分支命名 `feature/<task-id>-<kebab-desc>`；规范文档 `docs/COLLABORATIVE_DEV_WORKFLOW.md` v1.1；任务总表 `.workbuddy/tasks/TASKS.md`。
- 质量门禁：pytest绿+vitest绿+build干净+浏览器冒烟+代码审查+影响面Grep。
- **⚠️ 沙箱 git 孤儿分支坑（最高危）**：沙箱 `.git` 是残缺副本，孤儿分支（`git merge-base origin/main <branch>` 无输出）merge 进 main 会删光主干代码。开工前必查祖先关系；无输出时走「工作目录为准 + `git read-tree origin/main` 重建索引 + `git add -A` + 快进 push」同步，不 checkout。
- **⚠️ 沙箱 git 陈旧 .lock 阻塞 prune 坑**：`git branch -r` 残留已删远端分支根因是 `.lock` 陈旧锁（safe-delete 拦截 rm）。修复：`ctypes.windll.kernel32.DeleteFileW` 删锁+引用 → `git remote prune origin`；判定真伪用 `git ls-remote --heads origin`，勿信本地 `branch -r`。

## AI总结（WorkReport）模块
- 功能：自动生成日/周/月报（LLM 润色，不可用时规则兜底）；生成/查看/编辑/删除/定稿/邮件发送；定稿归档 Obsidian `15-工作总结/{类型}/{日期}.md`。
- **状态**：已合入 main（wr-1 b21e913 / wr-2 152576b / wr-3 3ecc47e）。后端 `backend/routers/work_report.py`(前缀 /api/v1/work-reports)；模型 `PmwbWorkReport`(表须含 `cc TEXT`)；前端 `WorkReportView.vue`(菜单「AI总结」)。改动 models.py/router 时勿删 AI总结 相关类与路由块。
