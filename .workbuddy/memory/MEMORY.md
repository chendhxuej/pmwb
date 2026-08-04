# PMWB 项目长期记忆

## 项目状态
- 前端 IA：首页看板 → **任务中心** → 需求与交付/运营监控/会议日程/**知识中心** + 邮件记录 + **重点工作**。任务中心聚合 6 类待办（个人待办/运营问题/开发工单/会议行动项/重点工作/需求催办），需求催办以 `pmwb_requirement_evaluation` 为准。
- 测试基线：后端 pytest 全绿、前端 Vitest 4/4、vite build 干净；GitHub: chendhxuej/pmwb (main)。

## 启动方案（看门狗常驻保活）
- **主方案**：`C:\pmwb-scripts\pmwb-keeper.py`（镜像 `scripts/`）每 15s 检查 3306/8000/5173/3210/8001，DOWN 用已验证控制台命令 DETACHED 拉起；后端/Master 等 3306 就绪才起。桌面双击 `启动PMWB.bat`（常驻看门狗，`--once`=一次性）。
- **一键重启**：桌面 `重启PMWB.bat` 双击即运行 `C:\pmwb-scripts\pmwb-restart.py`——按端口(3306/8000/5173/8001)终止现有前后端+MySQL+Master 进程并停旧看门狗，再后台拉起看门狗自动重新拉起全部服务；邮件中心(3210)独立不动。
- **开机自启铁律**：Startup 的 `pmwb-autostart.vbs` 必须 `cmd /c "<python.exe>" "<keeper.py>"`。**绝不能用 `pythonw`/`Run/Start-Process` 隐藏窗口直接拉 python.exe**——那样 `mysqld --console` 静默失败、数据库起不来。MySQL 控制台模式有父引导+子工作两个 mysqld.exe，属正常。
- **⚠️ 陈旧 PMWB 服务占位坑（高复发）**：本机曾有 3 个 PMWB-* NSSM 服务 + PMWB-MySQL 计划任务（已用 `scripts/uninstall-windows-services.bat` **右键管理员**永久删除）。若日后又出现「改了后端代码���不生效(返回404)」，先查是否残留旧服务占 8000；沙箱令牌被 UAC 过滤无法在沙箱内 `taskkill` 重启，需本机管理员操作。
- **⚠️ Ghost Port 坑（新增 2026-07-28）**：Python 进程被 Kill 后，TCP LISTENING socket 可能残留（netstat 显示 PID 但 process 不存在），看门狗 `port_up()` 误判服务运行→不启动新后端→用户看到过期代码。症状：`netstat` 端口有 PID 但 `taskkill /PID X` 报"没有找到进程"。修复：`Get-Process python | Stop-Process -Force` 全局清 Python 进程 + 重启 keeper。
- 服务化脚本(`install-windows-services.ps1` 等)已弃用，勿再迭代。

## 关键技术约定（高频坑）
- API：request.js baseURL='/api/v1'，api 文件用相对路径如 '/requirements'；拦截器 code===0 返回 data.data，禁止二次解包。
- `success()` 用 `message=`(非 `msg=`)，否则 TypeError→500。
- 时区：中国 UTC+8；统计用 `datetime.now(timezone(timedelta(hours=8)))`，库表 UTC 存、展示 ±8h，勿 utcnow 当本地今天。
- 前端日期空值传 `""` → Pydantic `Optional[date]` 422；Update schema 加 `@field_validator(mode="before")` 把 `""`/`None` 转 None。
- **图标引用坑**：数组字面量 `icon: Xxx` 立即求值，Xxx 必须已 import 且真实存在；漏 import/拼错→白屏，Rollup 不报错，**浏览器无头冒烟是必过项**。
- **菜单 hidden 坑**：`MainLayout.vue` 的 `menuItems` 必须 `.filter(c=>!c.meta?.hidden)` 才真正隐藏；meta 无 title 回退显示路由 name（难看英文）。
- python-docx：`doc.styles[name]`；链式 `anchor._element.addnext(new_p)`。需求交付附件删除 `filename` 用 `Body(embed=True)` 收 JSON，上传 `File(...)` multipart。
- 沙箱删守卫：Obsidian vault 路径 os.remove/rmtree 被沙箱拦截(409)，真实环境正常，勿改业务逻辑绕过。
- **⚠️ 沙箱 git 仓库残缺+对象库损坏坑（2026-08-01 实测修正）**：沙箱 `.git` 常是残缺副本（只跟踪十几~几十文件，`backend/main.py` 等不 tracked），且对象库可损坏（`fetch` 报 `missing blob`/`unresolved deltas`；`refs/stash`、`refs/heads/feature/*`、`.git/HEAD` 会被沙箱文件系统搞丢，致 `HEAD` 失效）。**直接 `git push` 当前残缺分支是可行的**——GitHub 上该分支 tree 视图不全（缺主干文件），但本次改动 blob 内容完整、PR 合入 `main` 时三方合并**不会删除 main 已有文件**（项目 `feature/ui-3-dashboard-polish` 等同模式分支已成功合入）。若需分支 tree 完整（独立构建/继续开发），须在本机完整仓库基于 `origin/main` 重建分支再推。推送后验证：`git ls-remote origin <branch>` 确认远端 SHA；`git show --stat <sha>` / `git ls-tree -r <sha>`（用本地对象库）确认改动文件都在。沙箱内不必反复修 HEAD/ref（写不持久化），远端已推送即达标。

## 架构整改约定（2026-07-25 审查落地）
- **催办/逾期判据单一来源**：`backend/utils/dateflags.py`（`is_overdue`/`is_due_soon`/`flag_due_date`/`relative_status`）；task_center/requirement/reminder 三处禁止各自实现，否则数字漂移。
- **邮件发送降级契约**：`EmailCenterClient.send_email(...)` 返回 `{"ok","data"?,"error"?}`；业务侧用 `raise_on_error=False` 并判 `result["ok"]`，失败只落 `send_status=failed`+记 `error_msg`，**不得抛异常中断接口**。超时 30s→10s。
- **配置强制环境变量**：`SECRET_KEY`/`DB_PASSWORD` 必填、从 `.env` 读取，缺失即报错；`DEBUG` 默认 False。加必填项须同步 `backend/.env` 与 README 示例。
- **sent_emails 索引**：`req_id` 已加 `ix_sent_emails_req_id`（迁移 20260725000002）；改模型索引须同步补 Alembic 迁移。
- 改 SQLAlchemy 模型(增/改列)后必须先 `alembic upgrade head` 再起后端（否则 1054 Unknown column→前端500）。
- **会议邮件收件人兼容「姓名/邮箱」**：`services/meeting.py send_mail` 的 `to`/`cc` 支持「中文姓名 或 邮箱」混合输入；非邮箱文本经 `MasterServiceClient.resolve_staff_emails` 走人员中台解析为邮箱，全部无法解析才报清晰错误（不再 400 裸拒）。前端 `MeetingView.vue` 邮件弹窗 `openMailDialog` 默认填参会人姓名即可，无需改回只收邮箱。

## 协同开发规范（2026-07-28 确立）
- **铁律**：禁止在 main 主干直接开发，所有改动走 feature 分支 → Vicky2号审查合版。
- **角色**：Vicky2号=集成者（拆任务/建分支/审查/合版/推送）；其他AI=开发者（分支上开发/自测/提交）；老大=决策者。
- **规范文档**：`docs/COLLABORATIVE_DEV_WORKFLOW.md` v1.1；任务总表 `.workbuddy/tasks/TASKS.md`。
- **Task Spec 必须自包含**：背景上下文+精确改动范围+可执行验收命令+禁止项清单+起点指引（跨 AI 不共享会话）。
- **分支命名**：`feature/<task-id>-<kebab-desc>`，task-id 格式 `<模块前缀>-<序号>`（如 mc-1）。
- **质量门禁**：pytest绿+vitest绿+build干净+浏览器冒烟+代码审查+影响面Grep。
- **异步审查反馈机制（v1.1 新增）**：Vicky2号审查发现问题 → 写 `.workbuddy/reviews/<task-id>-R<N>.md` 结构化反馈（P0/P1/P2 + 改进建议 + 项目约定引用）→ 晓伴修复后在回复区填修复记录 → Vicky2号重审。TASKS.md 状态流：🟡待审查 → 🔴审查退回 → 🟡待审查。每日自动化 `审查退回任务每日扫描` 监控退回项状态。
- **当前批次**：
  - 邮件中心整合 mc-1~5 ✅已合入主干（2026-07-28）。
  - 批次二·邮件中心优化：mc-opt-1 邮件统计概览 ✅已合入（7d2014d）。
  - 批次三·首页看板重构：db-1 ECharts组件 ✅已合入（0b6bbc0）、db-2 Dashboard接口 ✅已合入（f6b9406）；**db-3/4/5 因 P0（直接改旧首页 HomeView.vue 违反「新旧共存」策略）🔴审查退回**，晓伴需改走新建 DashboardV2View.vue + /dashboard-v2 路由。人员中台已于 2026-07-28 合入主干。

## 项目约定踩坑补充（2026-07-29）
- **`.gitignore` 放行**：`.workbuddy/{memory,reviews,tasks}/` 已放行纳入版本库（协同可见）；`automations/`、`scripts/` 仍忽略（可能含密钥/临时脚本）。改之前是整目录 `.workbuddy/` 忽略，导致审查记录对晓伴不可见，异步机制失效——已修复。
- **首页看板重构铁律（已调整 2026-08-03）**：原「db-3/4/5 确认 OK 前绝不允许改 `HomeView.vue`」**已被老大新指令覆盖**——2026-08-03 老大明确「直接优化旧版 HomeView」，故 `HomeView.vue` 现已允许直接迭代（本轮已补 5 类模块卡片 + 修 2 处口径）。原 db-3/4/5 审查退回方案（新建 `DashboardV2View.vue` + /dashboard-v2 路由）**已于 2026-08-03 应老大指令废弃并删除**（源文件、路由、旧 dist 产物已清，`vite build` 干净）；现仅保留旧版 `HomeView.vue` 为唯一看板页，后端 `get_dashboard()` 等聚合接口只服务此页。
