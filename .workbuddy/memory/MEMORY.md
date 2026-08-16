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
- 重启加固：pmwb-restart.py stop_all 已增强（taskkill 重试 3 轮 + PowerShell Stop-Process 兜底 + 端口释放校验）。

## 关键技术约定
- API：request.js baseURL='/api/v1'，拦截器 code===0 返回 data.data，禁二次解包；success() 用 message=（非 msg=）。
- 时区 UTC+8：新代码用 datetime.now() 或 db.models.now_cn；禁止 datetime.utcnow()。前端日期空值 → Update schema 加 field_validator(mode="before") 转 None。
- 图标：icon: Xxx 必须已 import；菜单 hidden 须 .filter(c=>!c.meta?.hidden)。
- SQLite/MySQL 方言：日期区间用 naive datetime 上下界（>= day_start, < day_end），勿 cast(col,Date)。
- 前端 basicData.js 路径坑：basic-data 类请求须相对路径 `'basic-data/...'`（无前导 `/`），否则 axios 丢 /api/v1 前缀；人员数据唯一源是 8001 中台。
- 抽屉草稿：composables/useDrawerDraft.js 统一 localStorage。

## 架构整改：邮件统一治理（核心，2026-08-16 规划）
- **设计意图**：所有发邮件触点走 `services/mail_dispatch.dispatch_email`（场景注册表 SCENES），正文经 `utils/markdown_mail.markdown_to_email_html`+统一签名，落库 EmailRecord。预览端点 POST /api/v1/mail-dispatch/preview。
- **现状失真（已查证）**：实际只有 meeting.py 走了门面；reminder/plugin/work_report/task_center/supervise 5 处**绕过门面直连** EmailCenterClient → 统一签名/HTML 样式/落库只在会议生效（周报·督办更不写 email_records）；前端 4 套预览分裂、周报预览≠实发。
- **已确认决策（写进计划文件）**：① 模板以 3210 服务端为事实源（按 type 渲染、运营零代码改文案）；② 全量收口（5 处迁门面 + 前端 4 套预览收敛为 1 个 MailComposeDialog）。计划：C:\Users\chend\.workbuddy\plans\quantum-nebula-newton.md。
- 默认签名 settings.EMAIL_SIGNATURE、本人 settings.SELF_NAME 在 core/config.py；3210 无签名概念，签名由 PMWB 内联注入。
- 催办/逾期单一来源：utils/dateflags.py。会议行动项分流：owner==SELF_NAME 建个人待办，否则走 action_dispatch 邮件（见 memory 旧条目细节）。会议收件人兼容「姓名/邮箱」，非邮箱经 MasterServiceClient.resolve_staff_emails。

## 协同开发/git 安全铁律
- 禁 main 直开发：feature 分支（feature/<task-id>-<kebab>）→ Vicky2号审查合版。质量门禁：pytest+vitest+build+浏览器冒烟+审查+Grep。
- **禁止 `git checkout -b`/`git branch`/`git worktree`**（沙箱偶发清空 .git/refs+logs 致本地 main 丢失，8/01 起反复）。提交统一走 `scripts/git-safe-commit.sh -m "msg" [--push] <文件...>`（自带 /d/fixbk_<ts> 备份 → 重锚 main → 精确 add → commit-gate 门禁 → commit）。
- 提交门禁 commit-gate.sh：import main 烟雾 + pytest --collect-only（紧急 PMWB_SKIP_GATE=1 跳过）。
- **浮动改动必提交**：no commit = not done；改完即提交，绝不"攒一批"过夜（8-15 灾难教训）。
- 孤儿分支 refs 清空恢复：git ls-remote origin main 取真实 SHA → reset --hard → update-ref → branch --set-upstream；本地未提交改动先 cp 到 /d/fixbk/。

## 验证纪律（铁律）
- 穿测须真实验证（TDD）：puppeteer 真实点击+DOM 断言+控制台错误捕获，禁以"页面能渲染"冒充。前端用 frontend/node_modules/puppeteer-core + 本机 Chrome。
- 运行态≠代码态：改完重启单实例 vite（清僵尸），curl/puppeteer 确认 5173 服务的是新代码。
- 基准对比先证伪：用 golden/备份当"好版本"前先 git/diff 确证其确为优化版。

## 模块纪要
- AI总结/WorkReport：routers/work_report.py(/api/v1/work-reports)，模型 PmwbWorkReport(含 cc)，前端 WorkReportView.vue；归档 Obsidian 15-工作总结/{类型}/{日期}.md。
- 大模型管理：pmwb_llm_provider 多模型注册表；routers/llm_provider.py；API Key 用 utils/secret.py XOR+Base64；call_best_available 全不可用时落规则模板。
- 知识标准化（产品圣经）：MAIN_NOTE_SECTIONS 14 章节；GET/PUT /knowledge/main-note/{domain_code}/section；ProductBibleView.vue+HubPanel.vue；§2.1 人工基线、AUTO 下沉 §2.3；旧 product_bible.py 已弃用。
- 主动运营分析（prod 工单）：PmwbOperationAnalysis 1:1 关联 issue；GET /analysis-template/download、POST /analysis/import、GET /issues/{id}/analysis；导入遗留任务只建运营工单不建 PmwbTodo。
