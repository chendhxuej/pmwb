# PMWB 项目长期记忆

## 邮件发送安全铁律（最高优先级，2026-09-01 事故后确立）
- **事故**：AI 用 curl 直打生产发信接口做"测试"，把测试邮件（含完整会议通知群发给 13 个外部单位）真发给同事；2026-09-07 二度事故：假域名 test@example.com 走 /task-center/send（无 dry_run）→ send_status=success（3210 投递失败未送达）。
- **硬约束（代码层）**：`dispatch_email` 新增 `confirm_send` 参数 + `settings.MAIL_DRY_RUN`（默认 True）。未带 `confirm_send=True` 只落库 email_records（send_status='dry_run'），绝不调 3210 真发。前端/系统自动发信均已固定带 confirm。收件人白名单 `MAIL_OWNER_EMAILS`。
- **AI 行为铁律**：①任何邮件自测一律 dry_run（不带 confirm_send），绝不向陈大海以外任何人真发；②验证=接口结构正确 + email_records 落库 + 3210 渲染成功，不需要真发；③真发只能老大页面显式点击；④自测只允许 (a) dispatch_email 不带 confirm (b) /mail-dispatch/preview (c) `_render_mail` 纯函数，**绝不用**真实邮箱 curl /task-center/send 或 /mail-dispatch/send；⑤收尾自审确认未向真实外部收件人发信。关闭 dry_run 仅限老大显式要求（.env MAIL_DRY_RUN=false）。

## 项目状态
- 技术栈：FastAPI + Vue3 + Element Plus + MySQL + Obsidian 联动；GitHub chendhxuej/pmwb (main)。拓扑：主后端 8000 / 人员中台 8001 / 前端 5173 / MySQL 3306 / 统一邮件中心 3210。
- 后端解释器：`backend/venv/Scripts/python.exe`（managed python 无项目依赖，勿用）。
- 前端 IA：首页看板 → 任务中心 → 需求与交付 → 运营监控 → 会议日程 → 个人待办 → 重点工作 → 人员中台 → 知识中心 → 邮件中心。

## Obsidian 知识中心铁律（2026-08-30 老大确认）
- 业务知识主笔记统一在 `01-业务知识` 下；`domain_group` 仅 4 值：商客业务/公共能力/系统平台/通用。禁止虚构中间层；四类分目录互不串门。
- 主笔记三类差异化模板（业务/系统平台/公共能力，同编号体系§1–§N语义不同不得混用）；分人工维护区/自动区/系统维护区，自动区须绑定事件源+写入格式、幂等回写、人工区零覆盖。
- 领域/主笔记页面化同步创建（走 obsidian_paths 权威源 build_main_note_skeleton），禁手工建；主笔记同步须同时查 DB 与 Obsidian 文件系统（domain_main_note_health/ensure_domain_main_notes）。
- 知识中心重构方案见 docs/知识中心优化方案评估.md。

## 启动/看门狗
- C:\pmwb-scripts\pmwb-keeper.py 每 15s 查 3306/8000/5173/3210/8001；后端启动命令 `venv/Scripts/python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000`。重启后端=taskkill 8000 PID，看门狗约 5-10s 自动拉起。
- 多实例防护：keeper.pid / restart.py .restart_lock / kill_keeper 三层清理。坑：kill Python 后 LISTENING 残留致看门狗误判；改代码不生效(404)先查旧 NSSM 服务。

## 关键技术约定
- API：request.js baseURL='/api/v1'，拦截器 code===0 返回 data.data；success() 用 message=（非 msg=）。
- 时区 UTC+8：datetime.now()/now_cn，禁 utcnow()。前端空日期 → Update schema field_validator(mode="before") 转 None。
- 图标 icon:Xxx 须 import；菜单 hidden 用 .filter(c=>!c.meta?.hidden)。
- 日期区间 naive datetime 上下界（>=day_start,<day_end），勿 cast(col,Date)。
- 前端 basic-data 请求须相对路径 'basic-data/...'；人员数据唯一源 8001 中台。
- 抽屉草稿 useDrawerDraft.js localStorage；业务领域下拉走缓存 loadBusinessDomains + refreshBusinessDomains 广播。
- 邮件模板变量状态字段须转译（3210 仅接收字符串，状态 value 禁直透）。
- API Key 加密与 SECRET_KEY 漂移坑（2026-08-30 根治）：密钥 XOR+Base64 存库，派生自 settings.SECRET_KEY；OS 环境变量 SECRET_KEY 会覆盖 .env → 全 provider 401。decrypt_secret 已加回退自愈（.env/pmwb-default-secret）。

## 需求与交付模块事故合集（2026-09-08~09-11）
- **dev_ticket_no 去重**：统一从 SentEmail 回填（`_eval_to_dict`、`pending_by_sa`），评估记录自身禁止写入（update allowed set 移除、create 不再设置）。⚠️后续事故（09-09 d53c887）：`pending_by_sa` 加了引用漏构造 map → NameError 致 /reminders/pending 500。**防复发：跨函数调整回填口径必须全文件 grep 确认"定义+引用"成对落地。**
- **AI 故事生成超时**：`US_STORY_LLM_MAX_TOKENS=16384`、`US_STORY_LLM_TIMEOUT=300`（注意 .env 优先于代码默认值，改完必须核 .env 实际值）；`storygen_llm.generate_via_unified()` 显式传参；前端 timeout 300s。
- **_eval_to_dict 缺 db 参数**（get_evaluations NameError）：加 `db: Session`。
- **接口规范/操作手册自动归档**：PmwbReqInterfaceDoc + PmwbReqManual 路由+前端卡片；上传自动归档 01-业务知识/{group}/{name}/05-交付物/。详情页初始化须调 loadInterfaceDocs 否则系统下拉"无数据"。
- **操作手册重复归档（09-11 根治 f0bd91e）**：upload_manual 不再兼容写 ext.deliverables（单一真相源 PmwbReqManual）；material_sync 自动归类并跳过历史兼容条目；sync_all 先 purge_manual_duplicates；主笔记 §6 读 PmwbReqManual。存量已清洗（scripts/cleanup_manual_duplicates.py + tests/test_material_manual_dedup.py）。

## 邮件统一治理与 HTML 渲染铁律（核心）
- 所有发信收口 dispatch_email（SCENES 12 场景）；预览 POST /api/v1/mail-dispatch/preview，发送 POST /api/v1/mail-dispatch/send。
- **正文由 PMWB 装配器渲染（2026-09-07 改造）**：11/13 场景 renderer=True 不调 3210 render_template；入口 `utils.mail_content.build_mail_body`（品牌色带+称呼+字段表+Markdown正文+签名）。新增场景须 MailScene 注册 + SCENE_META 配品牌色/标题/引导语 + SCENE_FIELDS 配字段。
- **统一宽度写法**：幽灵单元格 90% 居中（外层 100%+align=center，内层 width=90%）。**严禁 max-width:Npx;margin:0 auto**（Outlook 忽略偏左，Foxmail 固定窄列）。`_wrap_content_responsive` 为全项目唯一宽度写法。
- **会议类 widen_frame 后处理**（meeting_notice/minutes）装配器模式同样生效。
- **运营督办字段映射**：`build_ticket_fields` 把工单数据转 category/handler/resolveDate/description；纯文本 description 经 Markdown 段落渲染保留换行；extra_msg 注入「补充说明」。`/supervise/preview` 复用同一装配链路（预览即实发）。
- **督办邮件自动带出工单附件（2026-09-01）**：supervise 场景自动读 attachments + 真实文件，build_operation_attachment_block 注入清单 HTML（系统下载链接，公网配 PUBLIC_BASE_URL）+ 未超限真实文件转 base64 作 MIME 附件；单文件>20MB 或累计>50MB 跳过并在正文标注。清单须双写 desc/description 兼容。
- **督办邮件三坑（2026-09-12 修复 ac0b412）**：① MailComposeDialog 字段初值必须 `props.fieldValues || props.variables`（业务页统一传 :variables，只读 fieldValues 会让 supervise_*/research_* 有后端 schema 的场景字段表单与预览全空）；②「计划完成时间」字段源：运营工单 go_live_date→resolve_date 回退、开发工单 planned_finish_date（**无 plan_end 列**，裸取会 500）、需求 ext.version_required_date（嵌套子字典）——跨 ORM/dict 取值统一用 `_pick()`，禁裸属性访问；③ `routers/supervise.py` 严禁 `from . import supervise`（模块自导入致 /supervise/* 全 500），必须 `from services import supervise`。
- 邮件抬头：4px 品牌色带（日报/周报 #165dff、月报 #722ed1）；正式汇报邮件不用 emoji。
- 双栏卡片：内部 table height="260"、td valign="top"；_render_dual_overview 锚定 H2/Part B 字样，正则匹配标签写 <tag[^>]*>。
- _sanitize(bleach) 白名单 _ALLOWED_ATTRS 须含 align 与 height，否则居中/等高失效（"渲染有、发出去没有"）。
- 报告一级标题业务口径单一来源 report_prompt._TITLE_LABELS。
- 改完邮件渲染必须重启后端才生效；验证须渲染态 + _sanitize 发送态双校验。用户可控变量 html.escape() 防 XSS。

## 协同开发/git 安全
- 禁 main 直开发：feature 分支 → 审查合版；禁 git checkout -b/branch/worktree。提交走 scripts/git-safe-commit.sh（含 /d/fixbk 备份 → 重锚 main → 精确 add → commit-gate）。
- **沙箱 git 怪象（高发）**：脚本报「无改动跳过」但提交实际落盘、push 被吞；push 后本地 origin/main 跟踪引用不更新。**判断 origin 真实状态必须 `git ls-remote origin refs/heads/main`**，绝不用 git rev-parse origin/main。修正动作：git fetch origin main。
- 提交对象丢失恢复：直接跑 git-safe-commit.sh，勿手敲 checkout -b/reset --hard。
- Bash 会话 PATH 可能损坏（ls/head/grep/cd 不可用）：先 `export PATH="/c/Users/chend/.workbuddy/binaries/PortableGit/versions/1.2.0/bin:.../usr/bin:$PATH"`。

## 验证纪律
- 运行态≠代码态：改完重启后端/前端，curl/puppeteer 确认服务新代码。穿测须真实 DOM 断言，禁"能渲染"冒充。
- **vite build 通过 ≠ 页面能渲染（2026-09-11 白屏事故）**：Vue SFC 模板未声明变量编译能过、运行时崩卸载组件树 → 白屏。前端改动必做真实 DOM 断言。
- **前端编译冒烟禁用默认 `vite build`**（清 dist/assets >50 文件被 safe-delete 钩子拦截）。改用临时 outDir（`vite build --outDir <系统temp> --emptyOutDir`）再 grep 产物关键字符串。
- 现成工具：`frontend/tests/e2e/route-smoke.e2e.cjs`（遍历 17 个一级路由，断言 #app 非空 + 无 Vue 运行时错误）。新增/改动前端页面后必跑。
- 白屏排查三步（agent-browser）：① eval app.innerHTML 长度 → 0/正数判断；② console --clear → reload → console 拿 [Vue warn]（比 errors 可靠）；③ 对比已知正常路由区分全局/单页问题。
- 知识中心 E2E 模板 frontend/tests/e2e/knowledge-center.e2e.cjs；人员中台测试用 fake_master.py 替换 master_service_client._request。
- el-dropdown 默认 hover 触发，puppeteer 里须 page.mouse.hover 再点菜单项（DOM click 按钮不展开菜单）。

## 模块纪要
- AI总结/WorkReport：routers/work_report.py，归档 Obsidian 15-工作总结/{类型}/{日期}.md。周报生成超时三端对齐 900s（2026-09-12，前端 request.js/workReport.js/ai_qa.js + report_llm + DB provider timeout + .env US_STORY_*；.env 优先于代码默认值，改完核 .env）。
- 用户故事生成：落库=delete+insert 全量覆盖无缓存；**AI 失败必降级但不可静默**（logger.exception + fallback_reason，前端红色告警条，禁止伪装策略标签）。溯源 pmwb_user_story.gen_*。get_status 是真实连通探测（60s TTL）。
- 大模型管理：pmwb_llm_provider 多模型注册表；call_best_available 全不可用时落规则模板。
- 知识标准化（产品圣经）：MAIN_NOTE_SECTIONS 14 章节；GET/PUT /knowledge/main-note/{domain_code}/section。
- Obsidian 打开统一入口 openObsidianNote(relPath)，vault 固定「知识图谱」。
- 主动运营分析：PmwbOperationAnalysis 1:1 关联 issue。

## AI总结铁律
- 章节编号全链路同步（report_prompt 四处 + report_llm 兜底 + work_report 后处理正则），只改一处→矛盾。
- 需求去重按 _req_no() 数字归一；重点工作 active/tracking 分层，禁 is_active 一刀切。
- generate：max_tokens=16384、单 provider timeout=900s（2026-09-12 起，原 180s 不够 Kimi 8 章长文）、3 provider fallback；验证给足 240s+。
- 周报结构：第一章执行摘要（禁数字表）；第四章固定 4.1 高敏盯办/4.2 类别趋势/4.3 处理人时效/4.4 一线调研（独家归口）；高敏仅收未闭环 P0/P1。
