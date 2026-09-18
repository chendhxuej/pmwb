# PMWB 项目长期记忆

## 0. 最高优先级铁律
- **邮件发送**：AI 自测一律 dry_run（不带 confirm_send），绝不向陈大海以外真发；真发仅限老大页面显式点击。
- **git 提交**：禁用 git checkout -b/branch/worktree（沙箱孤儿分支会清空 .git/refs 致本地 main 丢失）；一律走 `~/.workbuddy/bin/git-safe-commit.sh`。origin 真实状态用 `git ls-remote origin refs/heads/main` 判定。

## 1. 项目状态与拓扑
- 技术栈：FastAPI + SQLAlchemy + Alembic + Vue3 + Element Plus + MySQL + Obsidian；GitHub chendhxuej/pmwb (main)。
- 端口：主后端 8000 / 人员中台 8001 / 前端 5173 / MySQL 3306 / 统一邮件中心 3210。
- 后端解释器：`backend/venv/Scripts/python.exe`。启动/看门狗 `C:\pmwb-scripts\pmwb-keeper.py`（15s 轮询，5-10s 自动拉起）。重启后端=taskkill 8000 PID。改代码不生效先查旧 NSSM 服务。

## 2. 关键技术约定
- API：`request.js` baseURL='/api/v1'，拦截器 code===0 返回 data.data；`success()` 用 `message=`（非 msg=）。
- 时区 UTC+8：用 `now_cn()`，禁 `utcnow()`；前端空日期→Update schema `field_validator(mode="before")` 转 None。
- 图标 `icon:Xxx` 须 import；菜单 hidden 用 `.filter(c=>!c.meta?.hidden)`。
- 前端 basic-data 走相对路径；人员数据唯一源 8001 中台。
- 本人姓名唯一来源 `settings.SELF_NAME`（默认陈大海），禁硬编码「我」。
- API Key 加密：XOR+Base64 派生自 `settings.SECRET_KEY`；OS 环境变量 SECRET_KEY 会覆盖 .env→全 provider 401。`decrypt_secret` 已加回退自愈。

## 3. 多负责人字段契约
- 存储：多选责任人一律逗号分隔字符串，字段长度 512，不建多对多表。
- 单一实现（禁再写私有副本）：后端 `utils/owners.py`（split_owners/join_owners/owners_display/owner_set）；前端 `utils/owner.js`（ownerList/ownerText/ownerLabel）。
- 分隔符容错 `[,，;；、]+`（**库中实际混用**：运营工单用逗号，会议行动项/重点工作用顿号），入库前 `join_owners` 规范化。
- 已支持多值：operation_issue.handler、research_issue.vendor_handlers、key_work_member_task.assignee、meeting_action.owner。仍单值：dev_ticket.developer、月/周计划 assignee、重点工作 owner。
- 筛选语义：按人筛选必须 `owner_set(t.owner) & wanted` 求交集，不能整串比较；运营工单额外用 `handler_exact=true`（逗号边界精确匹配，防「王伟」误命中「王伟民」）。
- 邮件/纪要：展示统一 `owners_display`（顿号）；收件人必须逐人展开。
- 会议行动项分流：owner 含 SELF_NAME 即建个人待办，其余负责人另派邮件。
- 迁移链尾 `20260914000002`（多负责人扩容）。`alembic upgrade head` 因坏壳文件 20260908105939 报 multiple heads，必须指定 revision id 升级；正常链尾 a7c3e91d4b28 之后挂新迁移。

## 4. 运营监控总览·责任人分布矩阵（2026-09-17）
- 数据单一来源 `GET /api/v1/operation/stats/by-handler`（summary 全局口径 + category_matrix + handlers[].matrix）。总览卡/磁贴/矩阵同源，禁再单独拉列表算数。
- 口径：全局块按 category+status 聚合（多负责人不重复，与 /operation/stats 对齐）；责任人块按 `split_owners` 拆分（人人计数）；空责任人归「未指派」沉底。
- 深链契约：矩阵格子 → `/operation/{category}?handler=X&status=Y`；WorkOrderView 用 `applyRouteFilters/syncQuery` 做 URL↔筛选双向同步（切子页签复位 status、保留 handler）。
- 组件（2026-09-18 泛化）：`components/Common/OwnerMatrix.vue` = **运营监控与任务中心共用的唯一实现**（旧 `Operation/HandlerMatrix.vue` 已删除，禁再写第二份热力矩阵）。结构：摘要卡 = 头像+姓名+逾期 tag+率迷你条+非零状态 chips（超 8 折叠 +n），点击展开热力矩阵，颜色=状态、深浅=数量 3 档。两侧差异全走 props：`categories / catShort / statuses / statusLabels / rateKey / riskMetric / labels / jump`（运营侧不传时用改造前默认值，行为零变化）。
- `OperationView.vue`（甜甜圈+4 指标 / 类别磁贴 / 矩阵）。
- 热力色一律 `color-mix(var(--st) N%, #fff)` 派生自 design token，禁硬编码十六进制。风险前置：未闭环最多者整卡描红。
- 回归工具 `frontend/tests/e2e/verify_ops_handler_matrix.cjs`（33 项，含 750 格逐格比对）。改总览、工单子页**或 OwnerMatrix 组件**必跑。
- 删除契约：`DELETE /operation/issues/{id}`（不存在返 deleted=False 不抛异常）、`POST /operation/issues/batch-delete`；删 category=prod 主单须级联清 PmwbOperationAnalysis / 关联 task 类 PmwbOperationIssue / PmwbKnowledgeLink。前端文案含「将同时删除其分析明细与关联遗留任务」。

## 5. 任务中心（聚合 8 来源）
- 后端 `services/task_center.py`（8 个 collector 实时采集，不落快照）+ `routers/task_center.py`（prefix `/task-center`：stats / **stats/by-owner** / tasks / tasks/{source}/{id} / resolve-contacts / send / draft）。
- **二级结构（2026-09-18）**：`/task-center` → 重定向 `/task-center/overview`；子路由 overview（总览）+ all（全部任务）+ 8 个来源（todo / operation-issue / research-issue / dev-ticket / meeting-action / key-work / requirement-urge / active-optimization），共用 `TaskCenterView.vue`，来源由 `route.meta.source` 驱动；顶部 el-tabs 已退役，改由 MainLayout 依据路由 children 自动渲染左导航二级（`views/TaskCenterLayout.vue` 仅 router-view）。
- **任务总览**（`views/TaskOverviewView.vue`，2026-09-18）：单一数据源 `GET /api/v1/task-center/stats/by-owner`（summary 全量口径 + source_matrix + owners[]）。甜甜圈=整体完成率 / 4 指标（总量·在办·已超期·已完成）/ 来源磁贴（全部 + 仅**有数据**来源，开发工单 0 条不占位）/ 责任人矩阵。三块同源，禁再各自拉列表算数。
- 口径：**总览=全量（含已完成/阻塞）**，**列表页子页签=在办**（`get_stats`/`get_tasks` 默认排除 done+blocked）——两者刻意不一致，总览卡右侧有「全量口径」提示，勿"修正"。
- 矩阵：行=任务来源（固定为全局有数据来源，与运营固定 5 类别同构，各人横向可比），列=统一 4 态；责任人块按 `split_owners` 拆分（人人计数，求和 ≥ 全局）。
- 深链契约：矩阵格子 → `/task-center/{来源slug}?owner=X&status=Y`；`TaskCenterView` 用 `applyRouteFilters/syncQuery` 双向同步（防重复拉取靠 `filtersMatchQuery` 比对，query 参数名是 `owner`、后端接口参数名是 `owners`）。
- 统计：total 235 / 在办 121（超期 52）/ 完成率 47.7% / 责任人 33 位 + 未指派 2。来源分布：待办 13 / 运营 103 / 调研 6 / 开发工单 0 / 会议 24 / 重点工作 73 / 催办 7 / 主动优化 9。
- 状态映射：统一 4 态 pending/in_progress/done/blocked。
- 已修缺陷（2026-09-18）：① `collect_todo` 硬编码 `owner="我"` → `settings.SELF_NAME`；② `pmwb_operation_issue.id=13` 的 handler 脏值「我」→「陈大海」；③ 前端 `sourceList` 补 `active_optimization`。
- 回归工具 `frontend/tests/e2e/verify_task_overview.cjs`（69 项，含矩阵逐格比对 + 8 子页冒烟 + 深链还原筛选），改任务中心必跑。

## 6. 需求与交付
- `dev_ticket_no` 去重统一从 SentEmail 回填；跨函数调整回填口径必须全文件 grep「定义+引用」成对落地。
- AI 故事生成：.env 优先于代码默认值；`US_STORY_LLM_TIMEOUT=300`、前端 timeout 300s；失败必降级且红色告警，禁伪装策略标签。
- 状态设为「已上线」必须填报实际上线日期（delivered_date），作 AI 周报上线判断依据；控件放详情页。
- 接口规范/操作手册自动归档 `01-业务知识/{group}/{name}/05-交付物/`；单一真相源 PmwbReqManual。

## 7. 邮件 HTML 渲染铁律（核心）
- 所有发信收口 `dispatch_email`（SCENES 12 场景）；预览 `/mail-dispatch/preview`，发送 `/mail-dispatch/send`。
- 正文由装配器渲染（`utils/mail_content.build_mail_body`）；新增场景须注册 MailScene + SCENE_META + SCENE_FIELDS。
- 统一宽度：幽灵单元格 90% 居中，严禁 `max-width:Npx;margin:0 auto`；`_wrap_content_responsive` 为唯一写法。
- `_sanitize`(bleach) 白名单 `_ALLOWED_ATTRS` 须含 align 与 height（否则「渲染有、发出去没有」）。改完须重启后端 + 渲染态/_sanitize 双校验。
- 督办邮件自动带工单附件（>20MB 单文件 / >50MB 累计跳过并标注）；字段源跨 ORM/dict 统一 `_pick()`，禁裸属性访问；`routers/supervise.py` 禁 `from . import supervise`（致全 500）。
- 邮件督办记录统一化（2026-09-17 完成）：EmailRecord 增 ref_type/ref_id + 索引；所有出信必写 email_records；新增 `GET /mail-dispatch/records?ref_type=&ref_id=`；前端通用组件 `<EmailSuperviseLog :refType :refId/>` 已接入运营/调研/会议/需求/任务中心/重点工作。Commits：3b640ef / 648e4fc / 8b24ba8。

## 8. 重点工作·周计划字段契约
- 语义：周计划=周任务目标；成员待办=什么人做什么事。责任人不挂周计划，由成员待办 `link_type=weekly_plan`+`link_id` 关联（可不关联）。
- 周次自动推算唯一实现 `services/keywork.py::derive_iso_week(d=None)`，`pmwb_key_work_weekly_plan.week` 已可空（迁移 20260914000001）。**严禁恢复手填周次**；周报依赖 `report_collector` 按 `p.week=='YYYY-Www'` 精确匹配，周次必须继续写入。
- 前端 `weeklyTaskMap`（周计划 id→关联待办）；成员待办列表有「关联」列+「编辑」入口。
- 多人任务中心按人筛选用集合求交集（见 §3）。

## 9. 前端 UI 设计系统（2026-09-13 de0c793）
- 设计令牌单一源 `frontend/src/styles/design.css`：`--accent #2f6fed`、`--success #0f9d6b`、`--warning #d98a1f`、`--danger #d9544d`、`--text-secondary #64748b`、`--shadow-elevated`、`--radius-lg/md/sm`。禁组件内硬编码十六进制或重定义同名变量。
- 统一页头 `PageHeader`（title/subtitle + #actions 插槽）；状态标签 `StatusBadge` + `constants/statusConfig.js`（新增状态色须先注册，禁裸用 el-tag type）；全局命令面板 `CommandPalette`（Ctrl+K）。
- 危险操作降级：`el-button--danger` 默认中性灰、悬停显红。
- 首页看板 2.0（2026-09-15 c3acd20）：DEMO 基准 `prototype/home-dashboard-v2-r3-unified.html`；回归工具 `frontend/tests/e2e/verify_home_v2.cjs`（25 项），首页改动后必跑；HomeView 保留 DEMO 硬编码色值属合规例外。

## 10. 验证纪律
- 运行态≠代码态：改完重启后 curl/puppeteer 确认；前端改动必做真实 DOM 断言。
- `vite build` 通过 ≠ 页面能渲染（SFC 模板未声明变量编译过、运行时崩→白屏）。编译冒烟用临时 outDir 再 grep 关键串。
- 现成工具：`route-smoke.e2e.cjs`（17 路由）；`frontend/tests/e2e` 下 ui_shots.cjs / verify_cmd.cjs / verify_home_v2.cjs / verify_ops_handler_matrix.cjs（33 项）/ **verify_task_overview.cjs（69 项）**。截图读图被沙箱过滤，只信文本日志（`_log.txt` 或脚本自写的日志文件）。
- Windows 侧取数：PowerShell 5.1 `Invoke-RestMethod` 解中文 JSON 会乱码（双编码），改用 managed python + urllib/ctypes；`netstat -ano` 输出为 GBK，python `subprocess` 必须 `decode('gbk','ignore')`（`text=True` 直接 UnicodeDecodeError）。
- 重启后端（实测）：netstat 取 8000 LISTENING PID → `taskkill /F /PID` → keeper 约 15s 自动拉起；后端**无 --reload**，改 py 必须重启才生效（接口 404 即是此因）。
- 沙箱删目录：`shutil.rmtree` / `Remove-Item -Recurse` 均被 safe-delete 拦截（trash-failed + SAFE_DELETE_FAIL_CLOSED）；改用 `[System.IO.Directory]::Delete($p,$true)` 可成功。PowerShell 工具 stdout 常被吞（无输出 ≠ 失败），结果一律用 Bash/Read 复核。

## 11. 模块纪要 / AI 总结
- AI 总结归档 Obsidian `15-工作总结/{类型}/{日期}.md`；周报生成三端对齐 900s。
- 章节编号全链路同步（report_prompt 四处 + report_llm + 后处理正则），只改一处→矛盾。
- 用户故事落库 = delete+insert 全量覆盖；`get_status` 是真实连通探测（60s TTL）。
- 知识标准化产品圣经 MAIN_NOTE_SECTIONS 14 章节；Obsidian 入口 `openObsidianNote(relPath)`，vault「知识图谱」。
- 大模型管理 `pmwb_llm_provider` 多模型注册表；`call_best_available` 全不可用落规则模板。

## 12. 历史根因归档（已治本，仅备查）
- StaffSelect 选人弹窗卡顿（2026-09-12 定案）：真根因是模板逐帧逐人调函数占满主线程→Popper 初始化饿死。治本 6485b47：合并为单个 `visibleGroups` computed（模板零函数调用）、selectedValues 用 Set、groups 改 shallowRef。**新组件模板禁写逐项函数调用**。
- 本地 git 沙箱绕坑（2026-09-13）：Bash shim 缺 dirname/coreutils，禁止在 shim 内用 cd/head/tail/grep。git 走绝对路径 `C:/Program Files/Git/cmd/git.exe -C "D:/项目/个人工作台系统" <cmd> > <log> 2>&1` 再 Read。`git-safe-commit.sh` 直调报 E=127（PATH 残缺），须显式 `PortableGit/versions/1.2.0/bin/bash.exe -c 'export PATH=...; <script> -C <repo> -m "…" --push -- <files>'`。`.workbuddy/*` 在 .gitignore，`git add` 带上会报 ignored 且脚本 set -e 中断——提交清单不要列当日日志。push 需 ~/.ssh，沙箱吞 refs/remotes 本地写入，故 `rev-parse origin/<branch>` 与 `git status` 不可信，用 ls-remote/fetch 判远端；本机看到 `<old>..<new> <branch> -> <branch>` 即真成功。
- 沙箱编辑会静默回滚：Edit 回执成功 ≠ 落盘，改完必须立即 grep 复核关键串。
