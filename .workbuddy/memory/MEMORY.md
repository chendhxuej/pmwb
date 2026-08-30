# PMWB 项目长期记忆

## 项目状态
- 技术栈：FastAPI + Vue3 + Element Plus + MySQL + Obsidian 联动；GitHub chendhxuej/pmwb (main)。拓扑：主后端 8000 / 人员中台 8001 / 前端 5173 / MySQL 3306 / 统一邮件中心 3210。
- 前端 IA：首页看板 → 任务中心 → 需求与交付 → 运营监控 → 会议日程 → 个人待办 → 重点工作 → 人员中台 → 知识中心 → 邮件中心。
- Obsidian 业务知识路径唯一化：`01-业务知识/商客业务/{领域名}/`。

## 启动/看门狗常驻
- `C:\pmwb-scripts\pmwb-keeper.py` 每 15s 查 3306/8000/5173/3210/8001，DOWN 用 DETACHED 拉起；桌面 启动PMWB.bat/重启PMWB.bat。
- 开机自启铁律：pmwb-autostart.vbs 必须 `cmd /c "<python>" "<keeper.py>"`，绝不用 pythonw/Run-StartProcess（mysqld 静默失败）。
- Ghost Port 坑：kill Python 后 LISTENING socket 残留 → 看门狗误判；`Get-Process python | Stop-Process -Force` 清掉重拉。
- 陈旧占位坑：改代码不生效(404)先查旧 NSSM 服务/PMWB-MySQL 任务是否占 8000。

## 关键技术约定
- API：request.js baseURL='/api/v1'，拦截器 code===0 返回 data.data，禁二次解包；success() 用 message=（非 msg=）。
- 时区 UTC+8：新代码用 datetime.now() 或 db.models.now_cn；禁止 datetime.utcnow()。前端日期空值 → Update schema 加 field_validator(mode="before") 转 None。
- 图标：icon: Xxx 必须已 import；菜单 hidden 须 .filter(c=>!c.meta?.hidden)。
- SQLite/MySQL 方言：日期区间用 naive datetime 上下界（>= day_start, < day_end），勿 cast(col,Date)。
- 前端 basicData.js 路径坑：basic-data 类请求须相对路径 `'basic-data/...'`（无前导 `/`），否则 axios 丢 /api/v1 前缀；人员数据唯一源是 8001 中台。
- 抽屉草稿：composables/useDrawerDraft.js 统一 localStorage。
- 业务领域下拉统一走缓存：前端通过 `loadBusinessDomains(params)` 加载，`BusinessDomainSelect` 挂载时订阅刷新；管理页新增/编辑/停用后必须调用 `refreshBusinessDomains()` 广播刷新。
- 邮件模板变量状态字段必须转译：3210 模板只接收字符串，状态 value 禁止直接透传，须在前端调用侧用各视图已有的 label 映射转中文。
- **API Key 加密与 SECRET_KEY 漂移坑（2026-08-30 实证，防复发）**：大模型/第三方 API Key 用 `utils/secret.py` 的 XOR+Base64 混淆存库，派生密钥取自 `settings.SECRET_KEY`；`core/config.py` 里 `SECRET_KEY: str` **无默认值、强制从环境变量读**。pydantic-settings 优先级是**真实 OS 环境变量 > .env 文件**，一旦 Windows 用户级（HKCU\Environment）设了 `SECRET_KEY`，就会**静默覆盖 .env** → 历史密文全部解不开 → `decrypt_secret()` 返回 `None` → `llm_provider.py` 的 `if key:` 不成立 → **不发 Authorization 头 → 401 Invalid Authentication**（表象"密钥失效"，实际密钥完好）。排查：查 `pmwb_llm_provider.api_key`，用候选 SECRET_KEY（OS 环境变量值 / .env 值 / `pmwb-default-secret`）逐一 `b64decode → XOR(sha256(secret)) → utf-8 decode`，能解出 `sk-` 前缀者即真正的加密密钥；用 winreg 读 `HKCU\Environment` 判断是否持久化。此坑是**全局**的（所有 provider 同时 401），别只盯报错的那个。**已根治（2026-08-30）**：① 把 Windows 用户级 `SECRET_KEY` 对齐为 .env 值；② `secret.py` 的 `decrypt_secret` 已加**回退自愈**（主密钥解不开依次回退 .env / `pmwb-default-secret`，`_looks_like_secret` 过滤乱码），今后任何 SECRET_KEY 漂移都能自动恢复，新增 API Key 加密点须复用此机制。

## 架构整改：邮件统一治理（核心，2026-08-16 规划，P0-P2 + T-A~T-F 全部完成 8/17）
- 设计意图：所有发邮件触点走 `services/mail_dispatch.dispatch_email`（SCENES 12 场景），正文经 `utils/markdown_mail.markdown_to_email_html`+统一签名，落库 EmailRecord。预览 POST /api/v1/mail-dispatch/preview，发送 POST /api/v1/mail-dispatch/send。
- 模板变量铁律：3210 引擎仅支持 `{{var}}`/`{{{var}}}`，无 if/each——列表变量调用方格式化后 `{{{tasks}}}` 透传。
- 默认签名 settings.EMAIL_SIGNATURE_MAP / SELF_NAME 在 core/config.py；3210 无签名概念，签名由 PMWB 内联注入（inject_signature_inline）。
- 报告一级标题业务口径：`商客市场能力建设与运营工作日报/周报/月报`，单一来源 `report_prompt._TITLE_LABELS`。

## 邮件 HTML 渲染铁律（防复发，2026-08-29~30 踩坑）
- 周报/月报内容容器**绝对居中**用「左右各 5% 幽灵单元格 + 中间 90% 内容区」；`align="center"` 仅作兜底。Foxmail/Outlook 对 table align 解析不稳，幽灵单元格法强制居中。严禁 `max-width` 与 `margin:0 auto`（通用 Markdown 邮件除外，仍用 max-width:680px）。
- 邮件抬头：4px 品牌色带（日报/周报 `#165dff`、月报 `#722ed1`）；正式汇报邮件不用 emoji。
- 双栏卡片：内部 table 统一 `height="260"`、内容 td `valign="top"` 等高起步；`_render_dual_overview` 提取 Part A/B 时结束条件须锚定「H2 章节标题/Part B 字样」，**不能锚定任意 `<strong>`**（列表项内 strong 误判导致溢出）。正则匹配 HTML 标签必须写 `<tag[^>]*>`。
- `_sanitize`（bleach）白名单 `_ALLOWED_ATTRS` **必须含 align 与 height**，否则被剥离 → 居中/等高失效（"渲染有、发出去没有"）。
- **改完邮件渲染必须重启后端**（`C:\pmwb-scripts\pmwb-restart.py`）才生效；验证须「渲染态 + `_sanitize()` 发送态」双校验。改完跑 `python scripts/gen_work_report_preview.py` 生成 `prototype/work-report-email-preview*.html` 切窗格宽度直观验证。用户可控变量 `html.escape()` 防 XSS。

## 协同开发/git 安全铁律
- 禁 main 直开发：feature 分支 → Vicky2号审查合版。禁止 `git checkout -b`/`git branch`/`git worktree`（沙箱偶发清空 .git/refs 致 main 丢失）。提交统一走 `scripts/git-safe-commit.sh -m "msg" [--push] <文件...>`（含 /d/fixbk 备份 → 重锚 main → 精确 add → commit-gate 门禁）。
- git push 后本地 `origin/main` 跟踪引用不更新（沙箱怪象）：判据以 `git ls-remote origin main` 为权威，勿信 `git status -sb` 的 ahead 计数；修正用 `sed` 改 `.git/packed-refs`（先备份）。
- 浮动改动必提交：no commit = not done。孤儿分支 refs 清空：git ls-remote 取真实 SHA → reset --hard → update-ref → set-upstream。
- **提交对象丢失恢复**（2026-08-30 实测）：commit 后 `git log` 报"无提交"、HEAD 游离、`git status` 全文件显示 `A`、且 `feature/xxx` 引用根本未建立——提交对象未持久化（沙箱怪象），但**工作树改动仍在**（先 `grep` 确认）。恢复：直接跑 `git-safe-commit.sh -m ... <文件>`（脚本内部 symbolic-ref 重锚 main + reset --mixed 清污染索引 + 仅 add 指定文件 + 提交），切勿手敲 `checkout -b`/`reset --hard`。仓库外备份在 `/d/fixbk_<ts>/`。feature 分支在本沙箱不可靠，统一入口脚本只落 main，属预期行为。

## 验证纪律（铁律）
- 穿测须真实验证（TDD，puppeteer 真实点击+DOM 断言+控制台错误捕获），禁以"页面能渲染"冒充。运行态≠代码态：改完重启单实例 vite（清僵尸），curl/puppeteer 确认服务的是新代码。基准对比先证伪。

## 模块纪要
- AI总结/WorkReport：routers/work_report.py(/api/v1/work-reports)，模型 PmwbWorkReport(含 cc)，前端 WorkReportView.vue；归档 Obsidian 15-工作总结/{类型}/{日期}.md。
- 大模型管理：pmwb_llm_provider 多模型注册表；API Key 用 utils/secret.py XOR+Base64；call_best_available 全不可用时落规则模板。
- 知识标准化（产品圣经）：MAIN_NOTE_SECTIONS 14 章节；GET/PUT /knowledge/main-note/{domain_code}/section。
- Obsidian 打开统一入口：`frontend/src/utils/obsidian.js` 的 `openObsidianNote(relPath)`，vault 固定「知识图谱」，禁止再 emit('open-note') 中转。
- 主动运营分析（prod 工单）：PmwbOperationAnalysis 1:1 关联 issue；导入遗留任务只建运营工单不建 PmwbTodo。
- AR总结排版：日报/周报方案A（蓝渐变头部+KPI条+双段式概述），月报方案B（紫仪表盘+6格KPI）。

## AI总结铁律（2026-08-29 确立，防复发）
- **章节编号全链路同步**：报告固定「一、本期概述 / 二、重点工作 / 三、需求与交付 / 四、运营支撑 / 五、会议与协同 / 六、个人待办 / 七、知识中心 / 八、下期重点计划」。增删章节须**四处同步**：①`report_prompt.py` 各章节描述 ②同文件「严格要求」编号清单 ③`report_llm.py` 规则兜底模板 ④`work_report.py` 后处理正则（H3→H2 提升）。只改一处 → prompt 自相矛盾、LLM 输出混乱。
- **新增数据模块走全链路**：采集器 `_collect_xxx()` → `collect()` 返回 → `report_dict.py` 转译+GLOSSARY → prompt 输入说明 → 章节指令 → `report_llm.py` 兜底。
- **需求去重**：同一需求存在「敏捷需求（2026）第（XXXX）号」与纯数字「XXXX」两种 req_id，须按 `_req_no()` 数字编号归一去重。added 桶须用组内任一记录 created 判定。
- **重点工作分层**：`active`（本期有实质活动详写）vs `tracking`（在途但本期无活动压缩一行）。禁 is_active 一刀切。
- **generate 耗时**：max_tokens=16384、单 provider timeout=180s，3 provider fallback 最长 540s+。验证须给足 240s+ 或走后台，禁因超时就宣布完成。
- **并行会话风险**：多 AI 共享工作树，改动可能被抢先提交。重要改动先 `cp` 到 `/d/fixbk/<主题>/`；若 `git status` 改动莫名消失，先 `git show HEAD:<file>` 比对，勿误判丢文件。
- **周报章节结构（2026-08-30 优化）**：① 第一章=执行摘要（判断+核心定调 3 条+本周攻坚 TOP3+处置时效预警，**禁数字表**）；② 第四章固定 4.1 高敏盯办(置顶,仅未闭环)/4.2 类别趋势/4.3 处理人时效/4.4 一线调研；③ 一线调研独家归口 4.4——运营采集器剥离标题含「领导调研」的工单（不计入运营总量/高敏/处理人时效），经 `_merge_research_tasks` 按归一化标题去重并入 research_issue（兼去调研表内部重复录入）；④ 高敏 `high_sensitivity` 仅收未闭环 P0/P1（排除 resolved/closed/verify/completed/done）。
