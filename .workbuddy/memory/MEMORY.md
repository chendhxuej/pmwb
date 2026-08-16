# PMWB 项目长期记忆

## 项目状态
- 技术栈：FastAPI + Vue3 + Element Plus + MySQL + Obsidian 联动；GitHub chendhxuej/pmwb (main)。服务拓扑：主后端 8000 / 人员中台 8001 / 前端 5173 / MySQL 3306 / 统一邮件中心 3210。
- 前端 IA：首页看板 → 任务中心 → 需求与交付 → 运营监控 → 会议日程 → 个人待办 → 重点工作 → 人员中台 → 知识中心 → 邮件中心。
- 业务知识联动：pmwb_business_domain 12 条种子；domain_code 已铺到业务表 + pmwb_knowledge_item。Obsidian 业务知识路径唯一化：`01-业务知识/商客业务/{领域名}/`。

## 启动方案（看门狗常驻保活）
- C:\pmwb-scripts\pmwb-keeper.py 每 15s 查 3306/8000/5173/3210/8001，DOWN 用 DETACHED 拉起；桌面 启动PMWB.bat / 重启PMWB.bat。
- 开机自启铁律：pmwb-autostart.vbs 必须 `cmd /c "<python>" "<keeper.py>"`，绝不用 pythonw/Run-StartProcess 隐藏窗口（mysqld 静默失败）。
- Ghost Port 坑：kill Python 后 LISTENING socket 残留 → 看门狗误判不拉新后端；`Get-Process python | Stop-Process -Force` 清掉重拉。
- 后端重启用 PowerShell `Stop-Process -Id <pid> -Force`（勿用 $pid 保留变量）；沙箱 taskkill 被拦截。
- 陈旧 PMWB 服务占位坑：改代码不生效(404)先查旧 NSSM 服务/PMWB-MySQL 任务是否占 8000。
- 重启脚本加固（2026-08-15）：pmwb-restart.py 的 stop_all 已增强——对 8000/5173 等端口 taskkill 重试至多 3 轮 + PowerShell `Stop-Process -Force` 兜底 + 端口释放校验，确保旧后端必被杀、看门狗必拉新代码。双击桌面「重启PMWB.bat」即可一键生效（若仍杀不掉，右键以管理员身份运行）。

## 关键技术约定
- API：request.js baseURL='/api/v1'，api 用相对路径；拦截器 code===0 返回 data.data，禁二次解包。success() 用 message=（非 msg=）。
- 时区中国 UTC+8（datetime.now(timezone(timedelta(hours=8)))）；前端日期空值 "" → Pydantic Optional[date] 422，Update schema 加 field_validator(mode="before") 转 None。
- 图标引用坑：icon: Xxx 必须已 import；菜单 hidden 须 .filter(c=>!c.meta?.hidden)。
- SQLite/MySQL 方言坑：日期区间统计用 naive datetime 上下界（>= day_start, < day_end），勿 cast(col,Date)。
- 抽屉草稿：composables/useDrawerDraft.js 统一 localStorage 草稿。
- 前端 basicData.js 路径坑：basic-data 类请求须用相对路径 `'basic-data/...'`（**无前导 `/`**），否则 axios 丢弃 `/api/v1` 前缀、dev 下 vite 不代理被 SPA fallback 挡成空数组。人员/组织/业务领域选择均走此 api；人员数据唯一来源是 8001 人员中台，中台挂掉则全站选人为空。

## 架构整改约定
- 催办/逾期单一来源：utils/dateflags.py（is_overdue/is_due_soon/flag_due_date/relative_status）。
- 邮件降级契约：EmailCenterClient.send_email 返回 {ok,data?,error?}；raise_on_error=False 判 ok，失败落 send_status=failed+error_msg。
- 统一邮件治理门面（2026-08-15 落地）：所有发邮件触点走 services/mail_dispatch.dispatch_email（场景注册表 SCENES：meeting_notice/meeting_minutes/action_dispatch/action_supervise/task_reminder/requirement_reminder），正文 html 统一经 utils/markdown_mail.markdown_to_email_html（Markdown→带内联样式HTML+统一签名，签名逐行转义防注入），text 追加 settings.EMAIL_SIGNATURE；预览端点 POST /api/v1/mail-dispatch/preview。新增触点须在 SCENES 注册场景，禁止各触点各写各的 EmailRecord/send_email。本人标识 settings.SELF_NAME、默认签名 settings.EMAIL_SIGNATURE 在 core/config.py。
- 会议行动项归属分流（2026-08-15）：PmwbMeetingAction 经 meeting.sync_action_todo 按 owner 分流——owner==settings.SELF_NAME 建个人待办(PmwbTodo)并回填 related_todo_id（个人待办中心可见）；否则作为团队任务走 action_dispatch 派发邮件，不进个人待办。owner 空抛 ValidationException。
- todo.related_id 存的是 PmwbMeeting.id（不是 PmwbMeetingAction.id）：sync_action_todo 写入处用 `related_id: str(meeting.id)`，反查服务 todo._build_related_title_map 按 meeting.id 查 PmwbMeeting.title；后端 routers/meeting.py::get_action 优先按 action_id 查、未命中按 meeting_id 查并返回「会议详情+该会议下 actions」kind='meeting'；前端 maDrawer 双兼容渲染。MeetingActionItemOut 不能直接 model_validate(PmwbMeetingAction)（缺 meeting_title/meeting_id_no/due_date 字段），手动构造 dict。
- 配置强制环境变量：SECRET_KEY/DB_PASSWORD 必填 .env；改模型列后先 alembic upgrade head 再起后端。
- Alembic 修订号：新建前 alembic heads 查号，取最大+1，down_revision 指向实际 head（20260804000001 已被 add_minutes_required 占用）。
- 会议邮件收件人兼容「姓名/邮箱」，非邮箱经 MasterServiceClient.resolve_staff_emails 解析。

## 协同开发规范（铁律）
- 禁 main 直开发：feature 分支 → Vicky2号审查合版。分支 feature/<task-id>-<kebab>。质量门禁：pytest+vitest+build+浏览器冒烟+审查+Grep。
- 沙箱 git 孤儿分支坑：孤儿分支 merge 进 main 删光代码；无祖先走「工作目录为准 + git read-tree origin/main + git add -A + 快进 push」不 checkout。
- 沙箱 git index 跨命令重置坑（已解决单命令法）：同一条 bash 内 `git symbolic-ref HEAD refs/heads/main` → `git reset --mixed main` → `git add <精确路径>` → `git commit` → `git push origin HEAD:refs/heads/feature/...`；add 后断言 `git diff --cached --name-only | grep -vE "^(frontend/src/|scripts/...)"` 检查。
- **孤儿分支致 refs 清空恢复（2026-08-16 实战）**：`git checkout -b` 等分支操作偶发把 `.git/refs/`、`git/logs` 清空、本地 main ref 丢失（远端完好）。恢复步骤：① `mkdir -p .git/refs/heads .git/refs/remotes/origin .git/logs`；② `git reset --hard <远端SHA>`（用 `git ls-remote origin main` 取真实 SHA，勿信本地 HEAD）；③ `git update-ref refs/remotes/origin/main <SHA>` + `git branch --set-upstream-to=origin/main main`；④ 若卡 `.git/index.lock` 先 `rm -f .git/index.lock`。本地未提交改动被 reset 冲掉前，务必先 `cp` 备份到仓库外（如 `/d/fixbk/`）。

## 验证与基准纪律（铁律，2026-08-15 夜间事故后确立）
- **浮动改动必提交**：任何前端/后端代码改动，改完即走 feature 分支提交入 main，禁止长期浮动在磁盘。8-15 git 灾难证明——浮动改动在 git refs 重建/文件覆盖后彻底丢失，且 golden tar 备份的也是"丢失后"状态，无法回滚。本次首页看板 8-12 优化因全程浮动未提交，灾难覆盖后永久丢失，被迫按 memory 文字规格重建（已重新提交 bdcf2d9）。
- **基准对比先证伪**：用 golden/备份 tar 当"已知好版本"基准前，必须先用 git/diff 确证该基准本身是当前优化版（而非已被覆盖的旧版）。本次误判：golden(12:37) 与磁盘 HomeView 一致，但两者都是旧版，diff 零差异被反向解读成"未降级"，实则都已降级。正确做法：对关键文件同时 grep 优化特征（如 greeting-inner 的 `justify-content:center`）确认基准是否真为优化版。
- **穿测须真实验证（TDD 精神）**：禁止以"页面能渲染""源码含函数定义"冒充"功能正常"。必须用 puppeteer 真实点击 + DOM 断言 + 控制台错误捕获；每个问题先定"理论值/预期状态"→ 真实操作 → 取"实测值"→ 判 pass/fail。截图仅供辅助，不能替代 DOM 断言。前端用 `frontend/node_modules/puppeteer-core` + 本机 Chrome(`C:/Program Files/Google/Chrome/Application/chrome.exe`) 可做无头端到端验证（注意 evaluate 内函数须内联，不能引用 Node 端变量）。
- **运行态≠代码态**：vite 僵尸实例/旧 dev server 会服务旧代码，导致"代码已修但页面仍坏"。改完必须重启单实例 vite（清僵尸），并用 curl/puppeteer 确认 5173 实际服务的是新代码。

## git 安全提交铁律（2026-08-16 整改后，针对 8/15 灾难）
- **禁止 `git checkout -b` / `git branch` / `git worktree`**：沙箱偶发清空 `.git/refs`+`logs` 致本地 main 丢失（grep 实证 8/01 起反复出现）。
- 提交统一走 `scripts/git-safe-commit.sh -m "msg" [--push] <文件...>`：自带仓库外 `/d/fixbk_<ts>` 备份 → 重锚 main（symbolic-ref+reset --mixed）→ 精确 add → commit-gate 门禁 → commit（--push 才推 origin/main）。
- 提交门禁 `scripts/commit-gate.sh`：`import main` 烟雾测试 + `pytest --collect-only`，已装 `.git/hooks/pre-commit`（紧急可 `PMWB_SKIP_GATE=1` 跳过）；直接拦住「整路由 NameError」「功能蒸发死测试」类回归。
- 安全网自动化：每日 13:40 WIP 自动提交（本地不 push）、09:05 浮动改动巡检（超 24h 提醒）、周五 12:10 测试符号扫描。
- **铁律重申**：no commit = not done；改完即提交，绝不"攒一批"，不再让浮动改动过夜。

## AI总结/大模型管理
- WorkReport 模块已合入 main；routers/work_report.py(前缀 /api/v1/work-reports)，模型 PmwbWorkReport（含 cc TEXT），前端 WorkReportView.vue。改动 models/router 勿删块。
- 大模型管理：表 pmwb_llm_provider（多模型注册表，is_default→priority fallback）；routers/llm_provider.py(前缀 /api/v1/llm-providers)；前端 LlmProviderManage.vue。API Key 用 utils/secret.py XOR+Base64，接口脱敏。报告走 services/llm_provider.call_best_available，全不可用时落规则模板；接入新模型需自备 API Key（OpenAI 兼容）。

## 知识标准化管理（原「产品圣经」，2026-08-13 路线B）
- 定位：知识中心「知识标准化管理」= 业务主笔记标准结构视图（14 章节）。MAIN_NOTE_SECTIONS：§1概述/§2.1产品矩阵(基线)/§2.2资费(基线)/§2.3产商品变更(AUTO)/§3.1服务场景(基线)/§3.2流程变更(AUTO)/§4.1规则(基线)/§4.2场景规则(AUTO)/§5变更轨迹(AUTO)/§6交付物(AUTO)/§7关联索引(system)/§8子笔记MOC(system)/§9时间线(AUTO)/§10关联系统。
- 端点（knowledge.py, /api/v1）：GET /knowledge/main-note/{domain_code}；PUT /knowledge/main-note/{domain_code}/section。实现 services/knowledge_link_service.py 的 get_main_note_structured/update_main_note_section/MAIN_NOTE_SECTIONS。
- 前端：ProductBibleView.vue + HubPanel.vue 左栏只读；API productBible.js（getMainNote/updateMainNoteSection）。
- 迁移：scripts/migrate_main_notes_kc4.py 将含「## 参考资料」旧主笔记重建标准结构（幂等，仅认参考资料块）；支持 --dry-run；执行前 .migrated.bak 备份。已 14 领域具标准内容，余 19 个标准空模板待填充。
- 时间线双源：business_timeline 聚合 pmwb_knowledge_link + domain_code 归属需求/会议/运营工单（去重）。"关联了但知识中心看不到"先查是 domain_code 还是 knowledge_link（见 8711643）。
- 坑：旧 product_bible.py GET /product-bible/{dc} 已弃用，前端勿调；§2.1 必须人工基线区、AUTO 变更下沉 §2.3。

## 主动运营分析子模块（运营工单 prod 类）
- prod 工单展示名：生产问题分析 → 主动运营分析（仅展示名，枚举值 prod 不变，零数据迁移）。
- 明细表 PmwbOperationAnalysis（1:1 关联 pmwb_operation_issue.issue_id，唯一）；迁移 20260815000001（down_revision=20260814000002）。
- 端点（/api/v1/operation）：GET /analysis-template/download（双sheet xlsx 模版：填写区+填写说明、遗留任务预置6空行）、POST /analysis/import（UploadFile，单事务建分析工单+明细+遗留任务工单）、GET /issues/{id}/analysis（明细+遗留任务子表）。
- 导入遗留任务自动同步：每条 → PmwbOperationIssue(category=task, issue_type=temp_task, related_req_id=分析工单号)，责任人经 services/staff_resolver.resolve_staff_id 解析，未匹配进返回 unmatched_handlers；只建运营工单、不建 PmwbTodo（q-1 决策）。
- 前端：WorkOrderView.vue 在 category==='prod' 时显示【下载模版】【导入】按钮 + 详情抽屉渲染分析明细与遗留任务子表；downloadTemplate 走 operationApi.downloadAnalysisTemplate()。
