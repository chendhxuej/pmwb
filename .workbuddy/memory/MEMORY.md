# PMWB 项目长期记忆

## 邮件发送安全铁律（2026-09-01 事故后确立，最高优先级）
- **事故**：AI 用 curl 直接打生产发信接口做"测试"，把测试邮件（含一封完整会议通知群发给 13 个外部单位）真发给了真实同事。这是严重外部操作事故。
- **硬约束（代码层）**：`dispatch_email` 新增 `confirm_send` 参数 + `settings.MAIL_DRY_RUN`（默认 True）。
  - 未收到 `confirm_send=True` 的请求**只落库 `email_records`（send_status='dry_run'），绝不调用 3210 真发**。
  - 前端真实点发送（`mailDispatch.sendEmail` / `meeting.sendMeetingMail`）已固定带 `confirm_send=true`；系统自动发信（周报/督办/提醒/任务中心/插件/重点工作/会议派发）服务端已传 `confirm_send=True`。
  - 收件人白名单 `MAIL_OWNER_EMAILS`（默认空）配置后生效，confirm 但超白名单记高危告警。
- **AI 行为铁律（不可违反）**：
  1. **任何邮件功能自测，一律走 dry_run（不带 confirm_send），绝不向陈大海以外的任何人真发邮件。**
  2. 验证邮件发送功能 = 确认接口返回结构正确 + `email_records` 落库（send_status 应为 dry_run 或 success）+ 3210 渲染成功。**不需要、也不允许真发。**
  3. 真发邮件只能由老大在页面上显式点击触发；AI 不得以任何理由（含"验证""测试"）用 curl/脚本向真实收件人发信。
  4. 收尾自审必须确认本次会话没有向真实外部收件人发出任何测试邮件。
- **关闭 dry_run（仅限老大显式要求全局真发验证）**：在 `.env` 设 `MAIL_DRY_RUN=false`。日常使用保持默认 True 即可，前端/系统均带 confirm_send 不受影响。

## 项目状态
- 技术栈：FastAPI + Vue3 + Element Plus + MySQL + Obsidian 联动；GitHub chendhxuej/pmwb (main)。拓扑：主后端 8000 / 人员中台 8001 / 前端 5173 / MySQL 3306 / 统一邮件中心 3210。
- 前端 IA：首页看板 → 任务中心 → 需求与交付 → 运营监控 → 会议日程 → 个人待办 → 重点工作 → 人员中台 → 知识中心 → 邮件中心。

## Obsidian 知识中心铁律（2026-08-30 老大确认）
- 业务知识主笔记统一在 `01-业务知识` 下；`domain_group` 仅 4 值：商客业务/公共能力/系统平台/通用。禁止"政企业务知识库"等虚构中间层。
- 四类分目录：商客业务/系统平台/公共能力/通用 分目录存放互不串门；商客业务目录不得存系统平台主笔记。
- 主笔记三类差异化模板（业务/系统平台/公共能力，同编号体系§1–§N但语义不同，不得混用）；分人工维护区/自动区/系统维护区，自动区须绑定事件源+写入格式、幂等回写、人工区零覆盖。
- 领域/主笔记页面化同步创建：新增子领域一键在 vault 建目录+主笔记（走 obsidian_paths 权威源 build_main_note_skeleton），禁手工建。
- 主笔记同步须同时查 DB 记录与 Obsidian 文件系统（domain_main_note_health/ensure_domain_main_notes，2026-08-31 修复）。
- 知识中心重构方案见 docs/知识中心优化方案评估.md。

## 启动/看门狗
- C:\pmwb-scripts\pmwb-keeper.py 每 15s 查 3306/8000/5173/3210/8001；桌面 启动/重启PMWB.bat。开机自启 vbs 用 cmd /c "<python>" "<keeper.py>"。
- 多实例防护：keeper.pid / restart.py .restart_lock / kill_keeper 三层清理。
- 坑：kill Python 后 LISTENING 残留致看门狗误判；改代码不生效(404)先查旧 NSSM 服务。

## 关键技术约定
- API：request.js baseURL='/api/v1'，拦截器 code===0 返回 data.data；success() 用 message=（非 msg=）。
- 时区 UTC+8：datetime.now()/now_cn，禁 utcnow()。前端空日期 → Update schema field_validator(mode="before") 转 None。
- 图标 icon:Xxx 须 import；菜单 hidden 用 .filter(c=>!c.meta?.hidden)。
- 日期区间 naive datetime 上下界（>=day_start,<day_end），勿 cast(col,Date)。
- 前端 basic-data 请求须相对路径 'basic-data/...'；人员数据唯一源 8001 中台。
- 抽屉草稿 useDrawerDraft.js localStorage；业务领域下拉走缓存 loadBusinessDomains + refreshBusinessDomains 广播。
- 邮件模板变量状态字段须转译（3210 仅接收字符串，状态 value 禁直透，前端调侧用 label 映射转中文）。
- API Key 加密与 SECRET_KEY 漂移坑（2026-08-30 根治）：密钥 XOR+Base64 存库，派生自 settings.SECRET_KEY；OS 环境变量 SECRET_KEY 会覆盖 .env → 全 provider 401。已加 decrypt_secret 回退自愈（.env/pmwb-default-secret）。

## 邮件统一治理与 HTML 渲染铁律（核心）
- 所有发信收口 dispatch_email（SCENES 12 场景）；预览 POST /api/v1/mail-dispatch/preview，发送 POST /api/v1/mail-dispatch/send。
- 统一宽度写法：**幽灵单元格 90% 居中**（左右各 5% + 中间 90%，align="center" 兜底）。**严禁 `max-width:Npx;margin:0 auto`**（Outlook 忽略→偏左，Foxmail 固定窄列）。`_wrap_content_responsive` 为全项目唯一宽度写法，周报已用；通用 Markdown 邮件（markdown_to_email_html）暂保留 680px 待统一方案全量执行。
- **3210 模板双层窄（根因）**：邮件 = 3210 frame(`max-width:600px`) 包裹 markdown_to_email_html 输出(`680px`)，双层叠加最窄。3210 是外部服务（模板存 3210 自有 DB，无 PUT/PATCH 更新接口、POST 行为不明、重启可能重置），故**PMWB 侧用 `widen_frame` 后处理改宽最稳可控**：meeting_notice/meeting_minutes 场景渲染后把外层 `max-width:600px`→`width:90%`、内层 `max-width:680px`→`width:100%`。其他 3210 场景（任务催办/督办/工单同步/需求催办等）暂保持，待统一方案批量处理。
- **运营监控督办邮件自动带出工单附件（2026-09-01）**：supervise_sync/supervise_urge 场景，`supervise_ticket` 自动读 `pmwb_operation_issue.attachments`（JSON 元信息 `{name,bytes,size}`）+ 真实文件 `uploads/operation/{id}/{name}`，经 `utils/operation_attachment.build_operation_attachment_block`：① 正文追加 HTML 附件清单（文件名+大小+系统下载链接 `http://{BACKEND_HOST}:{BACKEND_PORT}/api/v1/operation/issues/{id}/attachments/download`，公网部署配 `PUBLIC_BASE_URL` 覆盖）；② 未超限真实文件转 base64 作 `dispatch_email(attachments=)` 参数（真 MIME 附件）。超限策略：单文件>20MB 或累计>50MB 跳过并正文标注「体积过大未随信附上」。3210 supervise 模板用 `{{{description}}}` 变量（非 body），清单须 HTML 注入且**双写 `desc`/`description`** 兼容（历史传 desc）。预览端点 `/preview` 加 `attachmentIssueId` 参数复用同函数，保证「预览即实发」。前端 SuperviseDialog 加「预览」按钮调 `/preview`（iframe srcdoc 展示）。
- 邮件抬头：4px 品牌色带（日报/周报 #165dff、月报 #722ed1）；正式汇报邮件不用 emoji。
- 双栏卡片：内部 table height="260"、内容 td valign="top"；_render_dual_overview 提取 Part A/B 结束条件锚定 H2/Part B 字样，不能锚定任意 <strong>；正则匹配标签写 <tag[^>]*>。
- _sanitize(bleach) 白名单 _ALLOWED_ATTRS 须含 align 与 height，否则居中/等高失效（"渲染有、发出去没有"）。
- 报告一级标题业务口径：商客市场能力建设与运营工作日报/周报/月报，单一来源 report_prompt._TITLE_LABELS。
- 改完邮件渲染必须重启后端才生效；验证须渲染态 + _sanitize 发送态双校验。用户可控变量 html.escape() 防 XSS。

## 协同开发/git 安全
- 禁 main 直开发：feature 分支 → 审查合版；禁 git checkout -b/branch/worktree。提交走 scripts/git-safe-commit.sh（含 /d/fixbk 备份 → 重锚 main → 精确 add → commit-gate）。
- git push 后本地 origin/main 跟踪引用不更新（沙箱怪象）：判据以 git ls-remote 为权威；修正 sed .git/packed-refs。
- 提交对象丢失恢复：直接跑 git-safe-commit.sh（脚本重锚 main + reset --mixed + 仅 add 指定文件），勿手敲 checkout -b/reset --hard。

## 验证纪律
- 运行态≠代码态：改完重启后端/前端，curl/puppeteer 确认服务新代码。穿测须真实 DOM 断言，禁"能渲染"冒充。
- 知识中心 E2E 模板 frontend/tests/e2e/knowledge-center.e2e.cjs（puppeteer-core + 系统 Chrome）。
- 人员中台测试防御：fake_master.py 替换 master_service_client._request，离线零污染。

## 模块纪要
- AI总结/WorkReport：routers/work_report.py，归档 Obsidian 15-工作总结/{类型}/{日期}.md。
- 大模型管理：pmwb_llm_provider 多模型注册表；call_best_available 全不可用时落规则模板。
- 知识标准化（产品圣经）：MAIN_NOTE_SECTIONS 14 章节；GET/PUT /knowledge/main-note/{domain_code}/section。
- Obsidian 打开统一入口 openObsidianNote(relPath)，vault 固定「知识图谱」。
- 主动运营分析：PmwbOperationAnalysis 1:1 关联 issue。

## AI总结铁律
- 章节编号全链路同步（report_prompt 四处 + report_llm 兜底 + work_report 后处理正则），只改一处→矛盾。
- 需求去重按 _req_no() 数字归一；重点工作 active/tracking 分层，禁 is_active 一刀切。
- generate：max_tokens=16384、单 provider timeout=180s、3 provider fallback ≤540s+，验证给足 240s+。
- 周报结构：第一章执行摘要（禁数字表）；第四章固定 4.1 高敏盯办/4.2 类别趋势/4.3 处理人时效/4.4 一线调研（独家归口，运营采集器剥离"领导调研"工单）；高敏仅收未闭环 P0/P1。
