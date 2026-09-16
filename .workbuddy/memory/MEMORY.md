# PMWB 项目长期记忆（压缩版）

## 0. 最高优先级铁律
- **邮件发送安全铁律**：AI 自测一律 dry_run（不带 confirm_send），绝不向陈大海以外真发；真发仅限老大页面显式点击。详见「邮件渲染铁律」段。
- **git 安全提交铁律**：禁用 `git checkout -b/branch/worktree`（沙箱孤儿分支怪象会清空 .git/refs 致本地 main 丢失）；一律走 `scripts/git-safe-commit.sh`。origin 真实状态用 `git ls-remote origin refs/heads/main` 判定，勿用 `git rev-parse origin/main`。

## 1. 项目状态与拓扑
- 技术栈：FastAPI + Vue3 + Element Plus + MySQL + Obsidian 联动；GitHub chendhxuej/pmwb (main)。拓扑：主后端 8000 / 人员中台 8001 / 前端 5173 / MySQL 3306 / 统一邮件中心 3210。
- 后端解释器：`backend/venv/Scripts/python.exe`（managed python 无项目依赖，勿用）。
- 启动/看门狗：`C:\pmwb-scripts\pmwb-keeper.py` 每 15s 查 3306/8000/5173/3210/8001，~5-10s 自动拉起。重启后端=taskkill 8000 PID。坑：kill 后 LISTENING 残留致误判；改代码不生效先查旧 NSSM 服务。

## 2. StaffSelect 选人弹窗卡顿根因（2026-09-12 定案，勿重走弯路）
- 曾误判"内存换页"（重启后仍卡，证伪）与"IPv6/驱动劫持"（仅放大器，非根因）。
- **真根因**：模板里 `optionVisible/groupVisible/groupVisibleCount/isSelected` 逐帧逐人调用函数 → 每次重渲跑 ~370+ 次调用（含 `kw.split`）→ 主线程占满 → 点开下拉时 Popper 初始化被饿死 = 卡几秒。
- **治本（commit 6485b47）**：① 合并为单个 `visibleGroups` computed（模板零函数调用，每次交互只遍历一次）；② `selectedValues` 用 `Set` 做 O(1) 命中；③ `groups` 改 `shallowRef` 去深层 proxy。验证 `frontend/tests/e2e/verify_staff_fix2.cjs` 全过。
- 排查优先序：① 浏览器用 `127.0.0.1:5173` 对照（vite 需双栈 `server.host:true`；**keeper `ensure_frontend()` 硬编码 `--host 127.0.0.1` 会覆盖 vite.config.js**）；② 查 aTrust/DLP 驱动劫持；③ 机器层内存取证；④ 组件层最后查。
- 取证工具：PowerShell stdout 被环境吞，改用 bash + managed python（ctypes `GlobalMemoryStatusEx`）。

## 3. 关键技术约定
- API：`request.js` baseURL='/api/v1'，拦截器 `code===0` 返回 `data.data`；`success()` 用 `message=`（非 `msg=`）。
- 时区 UTC+8：`now_cn()`，禁 `utcnow()`；前端空日期→Update schema `field_validator(mode="before")` 转 None。
- 图标 `icon:Xxx` 须 import；菜单 hidden 用 `.filter(c=>!c.meta?.hidden)`。
- 前端 basic-data 走相对路径 `'basic-data/...'`；人员数据唯一源 8001 中台。
- API Key 加密：密钥 XOR+Base64 存库，派生自 `settings.SECRET_KEY`；OS 环境变量 `SECRET_KEY` 会覆盖 .env→全 provider 401。decrypt_secret 已加回退自愈（.env/pmwb-default-secret）。

## 4. 需求与交付防复发要点
- dev_ticket_no 去重统一从 SentEmail 回填；跨函数调整回填口径必须全文件 grep「定义+引用」成对落地（09-09 漏 map→NameError 500）。
- AI 故事生成：`.env` 优先于代码默认值，改完须核 .env；`US_STORY_LLM_TIMEOUT=300`、前端 timeout 300s；失败必降级且红色告警，禁伪装策略标签。
- 接口规范/操作手册自动归档 `01-业务知识/{group}/{name}/05-交付物/`；单一真相源 PmwbReqManual（09-11 根治重复归档）。

## 5. 邮件 HTML 渲染铁律（核心）
- 所有发信收口 `dispatch_email`（SCENES 12 场景）；预览 `/mail-dispatch/preview`，发送 `/mail-dispatch/send`。
- 正文由 PMWB 装配器渲染（`utils.mail_content.build_mail_body`）；新增场景须 MailScene 注册+SCENE_META+SCENE_FIELDS。
- 统一宽度：**幽灵单元格 90% 居中，严禁 `max-width:Npx;margin:0 auto`**；`_wrap_content_responsive` 为唯一写法。
- `_sanitize`(bleach) 白名单 `_ALLOWED_ATTRS` 须含 align 与 height（否则"渲染有、发出去没有"）。改完须重启后端 + 渲染态/_sanitize 双校验。
- 督办邮件自动带工单附件（>20MB 单文件 / >50MB 累计跳过标注）；字段源跨 ORM/dict 统一 `_pick()`，禁裸属性访问；`routers/supervise.py` 禁 `from . import supervise`（致全 500）。

## 6. 验证纪律
- 运行态≠代码态：改完重启后 curl/puppeteer 确认。前端改动必做真实 DOM 断言（禁"能渲染"冒充）。
- **vite build 通过 ≠ 页面能渲染**（SFC 模板未声明变量编译过、运行时崩→白屏）。编译冒烟用临时 outDir：`vite build --outDir <系统temp> --emptyOutDir` 再 grep 关键串。
- 现成工具：`frontend/tests/e2e/route-smoke.e2e.cjs`（17 路由断言）；白屏排查三步（app.innerHTML 长度→console [Vue warn]→对比正常路由）。

## 7. 模块纪要 / AI 总结铁律
- AI 总结归档 Obsidian `15-工作总结/{类型}/{日期}.md`；周报生成三端对齐 900s。
- 章节编号全链路同步（report_prompt 四处 + report_llm + 后处理正则），只改一处→矛盾。
- 用户故事落库=delete+insert 全量覆盖；get_status 是真实连通探测（60s TTL）。
- 知识标准化（产品圣经）MAIN_NOTE_SECTIONS 14 章节；Obsidian 入口 `openObsidianNote(relPath)`，vault「知识图谱」。
- 大模型管理 pmwb_llm_provider 多模型注册表；call_best_available 全不可用落规则模板。

## 8. 前端 UI 设计系统约定（2026-09-13，commit de0c793）
- **设计令牌单一源**：`frontend/src/styles/design.css` CSS 变量（`--accent #2f6fed`、`--success #0f9d6b`、`--warning #d98a1f`、`--danger #d9544d`、`--text-secondary #64748b`、`--shadow-elevated`、`--radius-lg/md/sm`）。**禁止**组件内硬编码十六进制色值或重定义同名变量。
- **统一页头**：`<PageHeader title subtitle><template #actions>`（`@/components/Common/PageHeader.vue`）。已迁移：RequirementDeliveryView / MailCenterLayout / MailRecordsView。
- **状态标签**：`<StatusBadge :label :type size>`（`@/components/Common/StatusBadge.vue` + `constants/statusConfig.js`）。新增状态色须先注册，**禁止**裸用 `<el-tag type="success/warning/danger">`。
- **全局命令面板**：`<CommandPalette v-model="open" />`（监听 Ctrl+K，从 router 聚合路由）。HomeView 已接入。
- **危险操作降级**：表格行内 `el-button--danger` 链接默认中性灰、悬停显红（design.css 全局规则）。
- **验证工具**：`frontend/tests/e2e/ui_shots.cjs`（10 页首屏截图 + `_log.txt` 含 len/scrollH/errs）+ `verify_cmd.cjs`。**截图读图被沙箱过滤**，只信 `_log.txt` 文本。

## 9. 本地 git 操作沙箱绕坑（2026-09-13）
- WorkBuddy Bash 的 `shell-runtime-bash-env.sh` 第 3 行 `dirname` 缺失 → `cd` 失败；coreutils（head/tail/grep/ls）也缺。**shim 内禁止 cd/head/tail/grep**。
- git 绕过法：绝对路径 `C:/Program Files/Git/cmd/git.exe -C "D:/项目/个人工作台系统" <cmd> > <log> 2>&1`，回 `echo "E=$?"`，再 Read 日志。
- 提交必须走 `~/.workbuddy/bin/git-safe-commit.sh -m "…" [--push] [--all | -- <files>]`（内置 detached HEAD 重锚 + 仓库外备份 + commit-gate 烟雾测试）。调用：`C:/Users/chend/.workbuddy/binaries/PortableGit/versions/1.2.0/bin/bash.exe "C:/Users/chend/.workbuddy/bin/git-safe-commit.sh" …`。
- **push 成功判定**：本机看 `<old>..<new> <branch> -> <branch>` 即真成功。**沙箱会吞 `refs/remotes/origin/<branch>` 本地写入**，故 `rev-parse origin/<branch>` 与 `git status` 不可信，必须用 ls-remote 或 fetch 输出判远端真实状态。

## 10. 运营监控工单删除契约（2026-09-14）
- **后端入口**：`DELETE /api/v1/operation/issues/{id}`（不存在返回 `deleted=False` 不抛异常）；`POST /api/v1/operation/issues/batch-delete`（`{ids:[int]}`）。
- **级联清理（防孤儿数据）**：删 `category=prod` 主工单时同步删 `PmwbOperationAnalysis`(issue_id 外键)、`PmwbOperationIssue`(category=task, related_req_id=主单 issue_no)、`PmwbKnowledgeLink`(source_type=operation, source_id=str(id))。service 层 `operation.py` 的 `delete()`/`batch_delete()`；router 在 `routers/operation.py`。
- **铁律**：改 operation 删除逻辑必须保留上述级联；前端提示文案含"将同时删除其分析明细与关联遗留任务"。

## 11. 重点工作周计划字段契约（2026-09-14）
- **语义**：周计划 = 周任务目标（这周要达成什么）；成员待办 = 什么人做什么事。责任人**不挂在周计划上**（界面已删「周次」「责任人」），由成员待办 `link_type=weekly_plan` + `link_id` 关联体现；成员待办**可不关联**。
- **周次自动推算**：`services/keywork.py: derive_iso_week(d=None)` 是**唯一实现**（router 建/改周计划、Excel 导入都调它）。`pmwb_key_work_weekly_plan.week` 已改为可空（迁移 `20260914000001`）。**严禁恢复让用户手填周次**。
- **周报依赖链**：`services/report_collector.py` 的「本周/下周计划」按 `p.week == 'YYYY-Www'` 精确匹配 → 周次必须继续自动写入，不能留 NULL。
- **联动实现**：前端 `weeklyTaskMap`（周计划 id → 关联待办列表，展示负责人+状态）双向可见；成员待办列表新增「关联」列与「编辑」入口（后端 PUT 早已存在）。
- **alembic 双 head 坑**：`20260908105939_add_pmwb_req_interface_doc_table.py` 是坏壳文件（`revision='%(rev)s'`、`down_revision=None`，模板变量未渲染），正常链尾是 `a7c3e91d4b28`；新迁移一律挂后者之后。
- **沙箱编辑会静默回滚（血泪教训）**：Edit 回执成功 ≠ 落盘。改完**必须立即 grep 复核关键串**（本次因 `_derive_iso_week` 未替换落盘导致接口 500 NameError）。

## 12. 多负责人字段契约（2026-09-14）
- **存储约定**：多选责任人一律 **逗号分隔字符串**（沿用运营监控工单 `handler` 的既有做法），**不建多对多表**。字段长度 512。历史单值数据天然兼容。
- **单一实现**：后端 `backend/utils/owners.py`（`split_owners`/`join_owners`/`owners_display`/`owner_set`）；前端 `frontend/src/utils/owner.js`（`ownerList`/`ownerText`/`ownerLabel`）。**禁止各处再写 split/join 私有副本**。
- **已支持多值的字段**：`pmwb_operation_issue.handler`、`pmwb_research_issue.vendor_handlers`、`pmwb_key_work_member_task.assignee`、`pmwb_meeting_action.owner`。仍是单值：`pmwb_dev_ticket.developer`、月计划/周计划 `assignee`、重点工作 `owner`。
- **入参容错**：逗号 / 顿号 / 分号混用均可，入库前统一 `join_owners` 规范化（routers/keywork.py 成员待办、services/meeting.py 行动项 update、keywork_excel 导入均已接）。
- **筛选语义**：任务中心「按人筛选」必须用集合求交集（`owner_set(t.owner) & wanted`），**不能整串比较** —— 否则一条任务挂 3 人时按任一人筛都筛不出来。
- **邮件/纪要不变量**：展示统一顿号（`owners_display`）；但**收件人必须逐人展开**（会议行动项派发/督办 `split_owners(owner)`）。
- **会议行动项分流**：owner 列表**含本人即建个人待办**（`SELF_NAME in owners`），其余负责人另行派发邮件。
- **迁移链尾**：现为 `20260914000002`（多负责人扩容）；再新迁移挂它之后。注意 `alembic upgrade head` 会因坏壳文件报 multiple heads，**必须指定 revision id 升级**。

## 13. 首页看板 2.0 统一规范版（2026-09-15，commit c3acd20）
- **DEMO 基准**：prototype/home-dashboard-v2-r3-unified.html 是唯一开发基准（行序：问候→KPI→模块概览6卡→快捷操作→核心工作区4卡→需求概览/今日聚焦/重点工作）；三风格过程稿同目录归档。
- **数据契约**：KpiItem.value_text（百分比串）；DashboardData.user_name="老大"、focus_items（今日聚焦6条超期优先）；LiveItem.source 五源混排（调研/运营/会议/需求/知识）；ModuleStats.aiCenter/materials + req.devCount + issues.researchTotal + knowledge.domainCount + task_center_dist.due_today；待写纪要=全量 count 非 limit(5)。
- **前端关键**：BentoCard header 多元素用 .head-extra 包装类；KPI num 取值必须写 k.value_text || (k.value ?? k.num ?? 0)——||与??混用不加括号 vite build 直接报错。
- **验证工具**：frontend/tests/e2e/verify_home_v2.cjs（23项：行序/老大问候/无陈工/KPI与接口4/4一致/NEW×2/含一线调研/去补录/首行两卡等高/console零fatal）。首页改动后必跑。
- **合规例外**：HomeView 保留 DEMO 硬编码色值（深色问候卡与 SVG 浅色系无对应令牌、#2f6fed=--accent 同值），替换会破坏与 DEMO 一致，属有意识例外。
- **遗留半成品（未提交，勿混入其他提交）**：backend/services/operation_analysis.py（运营分析Excel四布局解析增强）+ frontend/src/views/WorkOrderView.vue（导入提示加附件字段）仍在工作区，待单独验证后提交。

- **居中改版（e388749）**：模块概览 6 卡为纵排居中指标卡（数字→标签→描述中线对齐，水平+垂直双向居中）；实现靠 .mod-tile 挂类 + :deep(.card-body) flex 化（BentoCard 内部元素 scoped 选不到必须 :deep）。断言 D9/D10 已入 verify_home_v2.cjs。

- **NEW 徽标已移除（72db0b0）**：模块概览不再有 new-badge（老大 09-15 指令），verify_home_v2 D2 断言「无 NEW」，勿再加回。

- **推送验证铁律**（2026-09-15 复盘）：72db0b0c39c6fca8ddfe4d01742f0fab946a0c0f 在沙箱可能返回过期 stale value；**以 72db0b0c39c6fca8ddfe4d01742f0fab946a0c0f	refs/heads/main 返回的 SHA 为准**——与 HEAD 一致 = 推送真成功； 无输出 = 无未推送提交。
