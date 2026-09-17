# PMWB 项目长期记忆（压缩版）

## 0. 最高优先级铁律
- 邮件发送安全铁律：AI 自测一律 dry_run（不带 confirm_send），绝不向陈大海以外真发；真发仅限老大页面显式点击。
- git 安全提交铁律：禁用 git checkout -b/branch/worktree（沙箱孤儿分支怪象会清空 .git/refs 致本地 main 丢失）；一律走 ~/.workbuddy/bin/git-safe-commit.sh。origin 真实状态用 git ls-remote origin refs/heads/main 判定。

## 1. 项目状态与拓扑
- 技术栈：FastAPI + Vue3 + Element Plus + MySQL + Obsidian 联动；GitHub chendhxuej/pmwb (main)。拓扑：主后端 8000 / 人员中台 8001 / 前端 5173 / MySQL 3306 / 统一邮件中心 3210。
- 后端解释器：backend/venv/Scripts/python.exe。启动/看门狗：C:\pmwb-scripts\pmwb-keeper.py（每 15s 查端口，~5-10s 自动拉起）。重启后端=taskkill 8000 PID。改代码不生效先查旧 NSSM 服务。

## 2. StaffSelect 选人弹窗卡顿根因（2026-09-12 定案）
- 真根因：模板 optionVisible/groupVisible/isSelected 逐帧逐人调函数→主线程占满→Popper 初始化饿死=卡几秒。
- 治本(6485b47)：合并为单个 visibleGroups computed（模板零函数调用）；selectedValues 用 Set O(1)；groups 改 shallowRef。
- 排查优先序：① 浏览器 127.0.0.1:5173（vite 需 host:true；keeper ensure_frontend 硬编码 --host 127.0.0.1 覆盖 vite.config.js）；② aTrust/DLP 驱动劫持；③ 内存取证（PowerShell stdout 被吞，改用 bash+managed python ctypes）。

## 3. 关键技术约定
- API：request.js baseURL='/api/v1'，拦截器 code===0 返回 data.data；success() 用 message=（非 msg=）。
- 时区 UTC+8：now_cn()，禁 utcnow()；前端空日期→Update schema field_validator(mode="before") 转 None。
- 图标 icon:Xxx 须 import；菜单 hidden 用 .filter(c=>!c.meta?.hidden)。
- 前端 basic-data 走相对路径；人员数据唯一源 8001 中台。
- API Key 加密：XOR+Base64 存库派生自 settings.SECRET_KEY；OS 环境变量 SECRET_KEY 会覆盖 .env→全 provider 401。decrypt_secret 已加回退自愈。

## 4. 需求与交付
- dev_ticket_no 去重统一从 SentEmail 回填；跨函数调整回填口径必须全文件 grep「定义+引用」成对落地。
- AI 故事生成：.env 优先于代码默认值；US_STORY_LLM_TIMEOUT=300、前端 timeout 300s；失败必降级且红色告警，禁伪装策略标签。
- 接口规范/操作手册自动归档 01-业务知识/{group}/{name}/05-交付物/；单一真相源 PmwbReqManual。

## 5. 邮件 HTML 渲染铁律（核心）
- 所有发信收口 dispatch_email（SCENES 12 场景）；预览 /mail-dispatch/preview，发送 /mail-dispatch/send。
- 正文由 PMWB 装配器渲染（utils.mail_content.build_mail_body）；新增场景须 MailScene 注册+SCENE_META+SCENE_FIELDS。
- 统一宽度：幽灵单元格 90% 居中，严禁 max-width:Npx;margin:0 auto；_wrap_content_responsive 为唯一写法。
- _sanitize(bleach) 白名单 _ALLOWED_ATTRS 须含 align 与 height（否则"渲染有、发出去没有"）。改完须重启后端+渲染态/_sanitize 双校验。
- 督办邮件自动带工单附件（>20MB 单文件/>50MB 累计跳过标注）；字段源跨 ORM/dict 统一 _pick()，禁裸属性访问；routers/supervise.py 禁 from . import supervise（致全 500）。

## 6. 验证纪律
- 运行态≠代码态：改完重启后 curl/puppeteer 确认。前端改动必做真实 DOM 断言。
- vite build 通过 ≠ 页面能渲染（SFC 模板未声明变量编译过、运行时崩→白屏）。编译冒烟用临时 outDir 再 grep 关键串。
- 现成工具：route-smoke.e2e.cjs（17 路由）；frontend/tests/e2e 下 ui_shots.cjs / verify_cmd.cjs / verify_home_v2.cjs。截图读图被沙箱过滤，只信 _log.txt 文本。

## 7. 模块纪要 / AI 总结
- AI 总结归档 Obsidian 15-工作总结/{类型}/{日期}.md；周报生成三端对齐 900s。
- 章节编号全链路同步（report_prompt 四处+report_llm+后处理正则），只改一处→矛盾。
- 用户故事落库=delete+insert 全量覆盖；get_status 是真实连通探测（60s TTL）。
- 知识标准化产品圣经 MAIN_NOTE_SECTIONS 14 章节；Obsidian 入口 openObsidianNote(relPath)，vault「知识图谱」。
- 大模型管理 pmwb_llm_provider 多模型注册表；call_best_available 全不可用落规则模板。

## 8. 前端 UI 设计系统（2026-09-13 de0c793）
- 设计令牌单一源：frontend/src/styles/design.css CSS 变量（--accent #2f6fed、--success #0f9d6b、--warning #d98a1f、--danger #d9544d、--text-secondary #64748b、--shadow-elevated、--radius-lg/md/sm）。禁止组件内硬编码十六进制或重定义同名变量。
- 统一页头：PageHeader（title/subtitle + #actions 插槽）。已迁移 RequirementDeliveryView/MailCenterLayout/MailRecordsView。
- 状态标签：StatusBadge（label/type/size）+ constants/statusConfig.js。新增状态色须先注册，禁止裸用 el-tag type。
- 全局命令面板：CommandPalette（Ctrl+K）。HomeView 已接入。
- 危险操作降级：el-button--danger 默认中性灰、悬停显红。

## 9. 本地 git 沙箱绕坑（2026-09-13）
- WorkBuddy Bash 的 shell-runtime-bash-env.sh 第 3 行 dirname 缺失→cd 失败；coreutils 缺。shim 内禁止 cd/head/tail/grep。
- git 绕过：绝对路径 C:/Program Files/Git/cmd/git.exe -C "D:/项目/个人工作台系统" <cmd> > <log> 2>&1，回 echo "E=$?"，再 Read 日志。
- 提交走 git-safe-commit.sh -m "…" [--push] [--all | -- <files>]。
- push 成功判定：本机看 <old>..<new> <branch> -> <branch> 即真成功；沙箱吞 refs/remotes 本地写入，故 rev-parse origin/<branch> 与 git status 不可信，用 ls-remote/fetch 判远端。

## 10. 运营监控工单删除契约（2026-09-14）
- 后端入口：DELETE /api/v1/operation/issues/{id}（不存在返回 deleted=False 不抛异常）；POST /api/v1/operation/issues/batch-delete（{ids:[int]}）。
- 级联清理（防孤儿）：删 category=prod 主工单时同步删 PmwbOperationAnalysis(issue_id)、PmwbOperationIssue(category=task, related_req_id=主单 issue_no)、PmwbKnowledgeLink(source_type=operation, source_id=str(id))。service 层 operation.py delete()/batch_delete()；router routers/operation.py。
- 铁律：改删除逻辑必须保留级联；前端提示文案含"将同时删除其分析明细与关联遗留任务"。

## 11. 重点工作周计划字段契约（2026-09-14）
- 语义：周计划=周任务目标；成员待办=什么人做什么事。责任人不挂周计划，由成员待办 link_type=weekly_plan+link_id 关联；成员待办可不关联。
- 周次自动推算：services/keywork.py derive_iso_week(d=None) 是唯一实现；pmwb_key_work_weekly_plan.week 已可空（迁移 20260914000001）。严禁恢复让用户手填周次。
- 周报依赖链：report_collector 按 p.week=='YYYY-Www' 精确匹配→周次必须继续自动写入，不能留 NULL。
- 前端 weeklyTaskMap（周计划 id→关联待办）；成员待办列表「关联」列+「编辑」入口。
- alembic 双 head 坑：20260908105939 是坏壳文件，正常链尾 a7c3e91d4b28；新迁移挂后者之后。
- 沙箱编辑会静默回滚：Edit 回执成功≠落盘，改完必须立即 grep 复核关键串。

## 12. 多负责人字段契约（2026-09-14）
- 存储：多选责任人一律逗号分隔字符串（沿用运营工单 handler），不建多对多表，字段长度 512。
- 单一实现：后端 backend/utils/owners.py（split_owners/join_owners/owners_display/owner_set）；前端 frontend/src/utils/owner.js（ownerList/ownerText/ownerLabel）。禁止各处再写私有副本。
- 已支持多值：pmwb_operation_issue.handler、pmwb_research_issue.vendor_handlers、pmwb_key_work_member_task.assignee、pmwb_meeting_action.owner。仍单值：pmwb_dev_ticket.developer、月/周计划 assignee、重点工作 owner。
- 入参容错：逗号/顿号/分号混用均可，入库前 join_owners 规范化。
- 筛选语义：任务中心按人筛选用集合求交集 owner_set(t.owner)&wanted，不能整串比较。
- 邮件/纪要：展示统一顿号 owners_display；收件人必须逐人展开 split_owners(owner)。
- 会议行动项分流：owner 含本人即建个人待办（SELF_NAME in owners），其余负责人另派邮件。
- 迁移链尾现为 20260914000002（多负责人扩容）；再新迁移挂它之后。alembic upgrade head 因坏壳报 multiple heads，必须指定 revision id 升级。

## 13. 首页看板 2.0（2026-09-15 c3acd20）
- DEMO 基准：prototype/home-dashboard-v2-r3-unified.html 唯一基准。
- 验证工具：frontend/tests/e2e/verify_home_v2.cjs（25项）。首页改动后必跑。
- 合规例外：HomeView 保留 DEMO 硬编码色值（深色问候卡/SVG 浅色系无对应令牌）。
- 遗留半成品（未提交，勿混入其他提交）：backend/services/operation_analysis.py + frontend/src/views/WorkOrderView.vue 导入提示加附件字段，待单独验证后提交。

## 14. 邮件督办记录统一化（2026-09-17 本期任务）
- 问题：督办类邮件未稳定关联工单（遗留 /supervise/* 不落库；MailComposeDialog 落库但 req_id 恒 null）；前端展示为组件内存态（刷新即丢）；缺按工单查邮件的统一接口。
- 方案(P0 后端)：① EmailRecord 增 ref_type/ref_id 列+索引；② 所有出信经 dispatch_email 必写 email_records，弃用不落库旧路径；③ 新增 GET /mail-dispatch/records?ref_type=&ref_id=（回退 source+req_id）。
- 方案(P1 前端)：封装通用 <EmailSuperviseLog :refType :refId/> 组件，统一接入运营工单/一线调研/会议行动项/需求与交付/任务中心/重点工作明细页，替换前端内存态。
