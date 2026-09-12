# PMWB 项目长期记忆（压缩版）

## 0. 最高优先级铁律
- **邮件发送安全铁律**：AI 自测一律 dry_run（不带 confirm_send），绝不向陈大海以外真发；真发仅限老大页面显式点击。详见下方「邮件渲染铁律」段。
- **git 安全提交铁律**：禁用 `git checkout -b/branch/worktree`（沙箱孤儿分支怪象会清空 .git/refs 致本地 main 丢失）；一律走 `scripts/git-safe-commit.sh`。origin 真实状态用 `git ls-remote origin refs/heads/main` 判定，勿用 `git rev-parse origin/main`。

## 1. 项目状态与拓扑
- 技术栈：FastAPI + Vue3 + Element Plus + MySQL + Obsidian 联动；GitHub chendhxuej/pmwb (main)。拓扑：主后端 8000 / 人员中台 8001 / 前端 5173 / MySQL 3306 / 统一邮件中心 3210。
- 后端解释器：`backend/venv/Scripts/python.exe`（managed python 无项目依赖，勿用）。
- 启动/看门狗：`C:\pmwb-scripts\pmwb-keeper.py` 每 15s 查 3306/8000/5173/3210/8001，~5-10s 自动拉起。重启后端=taskkill 8000 PID。坑：kill 后 LISTENING 残留致误判；改代码不生效先查旧 NSSM 服务。

## 2. 老大机器环境（卡顿排查铁律，2026-09-12 修正）
- 物理内存 16GB，常驻全家桶（WorkBuddy×8~2.9GB、Kimi 桌面端~600MB、微信~300MB、Chrome/Edge、PMWB 全家桶）。**内存是卡顿放大器，非根因。**
- **选人弹窗卡顿根因复盘（关键！）**：最初误判"内存换页"；老大重启电脑后仍卡→该结论被证伪。实测定位两层叠加：
  1. **localhost IPv6 解析错配**：vite 仅监听 `127.0.0.1:5173`（IPv4），而 `localhost` 解析含 `::1`（IPv6），浏览器优先走 ::1 → 每请求先 IPv6 超时 ~2s 再回退 IPv4（实测 `[::1]:5173` 2.05s，`127.0.0.1:5173` 7ms）。
  2. **公司安全软件驱动层劫持**：机器常驻深信服 aTrust 零信任 + DLP（`SangforPWEx.exe`/`SangforUDProtectEx.exe`/`SangforPromoteService.exe` + `DlpAppData64.exe`/`TQDefender.exe`），hosts 被 aTrust 注入；其通过 WFP/LSP 驱动层劫持浏览器 localhost 流量（无头 curl 快、真实浏览器慢、无痕/重启均无效、重启自启）。系统代理 `ProxyEnable=0`，**排除系统代理劫持**。
- **排查优先序**：① 浏览器用 `http://127.0.0.1:5173` 替代 `localhost` 对照（定 IPv6 错配）；② 查 aTrust 客户端把 localhost/127.0.0.1 加信任白名单或临时退出验证（定驱动劫持）；③ 机器层取证（内存/提交量）；④ 代码层最后查。
- **网络层优化已落地（非主因，2026-09-12 验证）**：双栈监听根治 IPv6 错配——① `frontend/vite.config.js` 改 `server.host: true`；② **关键坑：`pmwb-keeper.py` 的 `ensure_frontend()` 硬编码 `--host 127.0.0.1` 覆盖 vite.config.js**（CLI>配置），同步改 `--host ::` 并重启 keeper。实测选人弹窗 API 请求由递增劣化(130→1388ms)降为平稳(77→332ms)。**但老大真实 Chrome 仍卡（5s 冻结）→ 证伪"IPv6=根因"，IPv6 仅放大器。** 现状：临时 vite 双栈 + keeper(PID 5396)兜底保活。
- **根因转向组件方案（2026-09-12 老大指正）**："全站唯独 StaffSelect 的组织/身份筛选卡"具组件特定性 → 根因在组件交互/数据方案，非系统环境。方案缺陷：① 筛选器(filterOrg/filterRole)强联动 `filteredGroups`（客户端全量过滤 93 人×16 组 → 重渲含 el-checkbox 的人员列表）；② dialog 无 `destroy-on-close`，mounted 即加载全量、`append-to-body` 常驻重组件；③ `filteredGroups` 每次返回全新 `{...g}` 对象破坏 Vue 复用（patch 退化为 remount el-checkbox）；④ 下拉"打开"瞬间同步渲染几十个 el-option popper（弹层渲染跳，搜索框无此跳）。对照：全站其他 el-select 是孤立表单字段，改值不触发重组件列表重渲 → 故唯独它卡。
- **取证工具**：PowerShell stdout 被环境吞，改用 bash + managed python（ctypes `GlobalMemoryStatusEx` / `typeperf`，typeperf 输出 GBK）。
- StaffSelect 组件本身无内存泄漏/定时器风暴（dev 模式组织/身份筛选 ~100-200ms 固定开销）；但**方案层"筛选器↔大列表强联动+常驻不销毁+每次重建 vnode"**是真实浏览器卡顿的结构性来源。诊断脚本留存 `frontend/tests/e2e/diag_*.cjs` 与 `verify_ipv6_lag.cjs`。
- **组件层修复（两层，2026-09-12）**：
  - **第一层（commit 00262a7，改善有限）**：三改——① 移除 93 个 `el-checkbox` 重组件，改 CSS 轻量 `<span class="staff-picker-check">`；② 筛选由 `filteredGroups` 重建整表改为全量渲染 + `v-show` 显隐；③ dialog 加 `destroy-on-close`。老大实测"有所改善但不明显" → 说明 el-checkbox/v-show 不是主因。
  - **第二层（commit 6485b47，真正治本）**：真正的卡顿源是**模板里 `optionVisible/groupVisible/groupVisibleCount/isSelected` 四个函数逐帧逐人调用**——每次重渲（哪怕 hover/选中态变化）都跑 ~370+ 次函数调用（每次 optionVisible 还做 `kw.split` 字符串操作），93 人列表始终全量挂载 → 主线程被占满 → 点开下拉时 Popper 初始化被饿死 = 卡几秒。**E 定案实验（127.0.0.1 仍卡）已排除网络层，钉死根因在组件渲染本身。** 修复：① 合并为**单个 `visibleGroups` computed**（每次交互只遍历 93 人一次，模板零函数调用）；② `selectedValues` 内用 `Set` 做 O(1) 命中；③ `groups` 改 `shallowRef` 去深层 proxy。外观/交互/多选/全选/搜索全部保留。验证 `frontend/tests/e2e/verify_staff_fix2.cjs` 全过（el-checkbox=0、93 轻量勾选框、默认全量 93、搜索筛选生效、多选/全选/确认正确、无 console error）。**元结论：IPv6/驱动劫持仅放大器；组件层"模板逐人函数调用"才是真根因，C+B 治本。**

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
