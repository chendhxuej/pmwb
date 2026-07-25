# 产品经理个人工作台系统 (PMWB) — 架构深度审查报告

- 审查日期：2026-07-25
- 审查视角：资深软件架构师
- 审查范围：后端（FastAPI + SQLAlchemy + MySQL）、前端（Vue3 + Element Plus + Vite）、工程化 / DevOps / 技术债
- 方法：三路并行静态探查（后端 / 前端 / 跨切面）+ 关键事实本地复核（git 状态、.gitignore、config.py）
- 总体健康度评分：**6 / 10**（骨架良好——Alembic、测试、统一异常层、部署脚本齐全；但工作树处于易碎的半成品状态，且存在安全默认、运维脆弱、前端重复度高等问题）

---

## 一、执行摘要（给产品视角看）

系统**整体能跑、方向对**，但当前有三个"会咬人"的隐患和一个"已经咬了"的事实：

1. **工作区里堆了 30 处没提交的改动，且相互耦合**——其中 `basic_data` 模块被 `main.py` 引用却没有提交，万一你或工具只提交部分文件，后端会直接 `ImportError` 起不来。
2. **你电脑上跑的后端是旧版本**（localhost:8000 那个进程没重启过）。我们刚修好的"需求催办判断条件"在线上**根本没生效**，任务中心仍显示 18 条。这是已发生的事实，不是推测。
3. **"要不要催 / 超没超期"这种判断逻辑，代码里写了三遍**，分属不同模块。今天只修了其中两处，将来改一处忘两处，数据就会对不上。
4. 安全上有"无配置即弱密码"的默认风险；重点工作模块保存时若中途出错可能只存一半；发邮件是"卡住等"的，邮件中心一慢整个系统跟着卡。

下面按优先级展开，每个问题都给了**文件:行号证据**和**业务影响**。

---

## 二、🔴 P0 — 当前就会出事 / 数据正确性（最高优先级）

### P0-1 工作区耦合混乱，误提交会导致后端起不来
- 证据：`main.py:14,112` 引用 `basic_data`，但 `backend/routers/schemas/services/basic_data.py` 全部 `??`（untracked）；`git status --short` 共 **30 处**（11 modified / 18 untracked，含 `staff.js` 删除）。
- 业务影响：如果只 `git add main.py` 提交，`basic_data` 文件不在仓库，启动即 `ImportError`，整个后端挂掉。
- 建议：**要么把 basic_data 整套（含迁移、router、schema、service、前端、seed）作为一次原子提交；要么在它做完之前，先把 `main.py` 里的 basic_data 引用摘掉**，等该模块完成再接回。绝不允许"半提交"。

### P0-2 线上跑的是旧代码（stale deploy），修复未生效
- 证据：运行日志 `logs/pmwb_20260725.log` 仍出现 `WHERE sent_emails.is_involved=... AND coalesce(sent_emails.workload,...)` 旧查询；今日 commit `5c706b4` 已把判据改为评估表口径，但 localhost:8000 旧进程没重启。
- 业务影响：**"需求催办"现在显示 18 条，实际应是 2 条**（修复逻辑没生效）。这就是你之前觉得"信息不准"的根因，且目前线上仍是错的。
- 建议：**你本地重启一次后端**（杀掉 8000 进程重跑 `python main.py`），修复立即生效。同时应建立"改完代码必须重启/重载"的受控流程（见 P1-7）。

### P0-3 催办 / 逾期判据三套并存，未来必漂移
- 证据：`task_center.py:105-110`（`is_overdue/is_due_soon`）、`requirement.py:80-96`（`overdue/warning/on_track`）、`reminder.py` 各自实现；今日仅修了 `task_center` 与 `requirement` 两处。
- 业务影响：同一笔需求"该不该催"，在三处可能算出不同结论，久了数据互相矛盾，谁也说不清哪个准。
- 建议：收敛为**单一判据函数 / 判据服务**，三处统一调用。

---

## 三、🟠 P1 — 安全 / 数据完整性 / 性能（高优）

### P1-1 配置硬编码弱默认密码（无 .env 即弱凭证）
- 证据：`core/config.py:10` `SECRET_KEY="your-secret-key-change-in-production"`；`config.py:16` `DB_PASSWORD="123456"`。
- 说明：`.env` 已被 gitignore（安全），但**默认值本身就是弱密码**。一旦部署环境漏配 `.env`，系统用弱密码连库、用公开 SECRET 签名。
- 建议：去掉默认值，改为**强制环境变量**；`SECRET_KEY` 用强随机生成；`DEBUG` 默认 `False`。

### P1-2 重点工作模块在 HTTP 层直接写库，分步 commit 无回滚
- 证据：`routers/keywork.py:117-310` 在路由内对六张子表 `db.add/commit`，且无整体事务包裹；`BaseService.create/update/delete`（`base.py:57-81`）也是 commit 无 `try/rollback`。
- 业务影响：保存重点任务时若中途失败，**可能只存了主任务、子任务/成员缺失**，留下半成品数据。
- 建议：业务逻辑移入 `services/keywork.py`，用**单事务**包裹，失败整体回滚。

### P1-3 任务中心实时全表聚合 + `sent_emails` 无索引
- 证据：`services/task_center.py:124-470` 每个 collector 全表 `.all()`，在 Python 内存筛选分页；`db/models.py:488-510` 的 `sent_emails` 无任何索引，却高频按 `req_id` 查询（`requirement.py:168,253,287,323`）。
- 业务影响（诚实校准）：**当前数据量几千条，实时聚合其实不慢**，不是燃眉之急。真正该修的是 `sent_emails.req_id` 缺索引——数据长到几万条后查询会变慢。属于"现在花 10 分钟修、避免将来背锅"项。
- 建议：给 `sent_emails.req_id` 加索引；任务中心保持实时聚合即可（单机单用户不必上缓存/快照表，避免过度设计），但分页应下沉到 DB 层。

### P1-4 邮件中心同步阻塞调用 + 串行 N+1 通讯录解析
- 证据：`utils/email.py:15` 同步 `httpx.Client`；`utils/email.py:74-92` 按姓名循环串行 GET 解析邮箱；路由全为同步 `def`，由线程池执行。
- 业务影响：发邮件是"卡住等"。邮件中心（localhost:3210）一慢或挂，**所有同步接口线程被占满，整个系统其他功能也卡住**（最长 30s 阻塞）。
- 建议：发信改**后台任务 / 异步**，加超时+重试+失败降级（落记录但不 500）；通讯录解析改批量接口一次到位。

### P1-5 统一异常信封被部分绕过
- 证据：`core/response.py` 定义 `{code,message,data}` 信封，但 `keywork.py:353,355`、`requirement_delivery.py:65,82,84` 直接 `raise HTTPException`，返回 `{"detail":...}`，前端需同时兼容两种格式。
- 建议：统一走 `PMWBException` 信封，禁止路由里裸 `HTTPException`。

---

## 四、🟡 P2 — 架构与一致性（中优）

### P2-1 后端分层破坏（router 内含业务）
- 证据：`routers/keywork.py`、`routers/requirement_delivery.py:78` 在路由内直接 `db.query/add`。
- 建议：router 只做参数校验与响应装配，业务进 service。

### P2-2 前端 `TaskCenterView.vue` 732 行巨型组件 + 双套邮件接口并存
- 证据：`TaskCenterView.vue`（732 行）聚合 6 类来源 + 需求催办 Tab；内部 `emailDialog`（taskCenter 接口）与 `urgeDialog`（reminder 接口）双套并行，逻辑重复。
- 业务影响：改一处容易漏另一处；后续维护成本高。
- 建议：拆为 `StatsBar / UnifiedTaskTable / UrgeBySaTab / TaskDetailDrawer / EmailComposeDialog` 5 个子组件 + `useTaskCenter` 组合式；合并 taskCenter/reminder 邮件能力。

### P2-3 前端跨视图代码重复率 ~60%，公共组件采用率低
- 证据：`Common/DataTable.vue` 仅 2/23 视图使用；表格+筛选+分页+邮件对话框+状态色映射在 RequirementDeliveryView / WorkOrderView / TaskCenterView / MailRecordsView 各自重写。
- 建议：抽 `EmailComposeDialog` + `useMailCompose` 组合式；`constants/` 空目录应放 `statusTagMap`/`priorityColorMap`；强制复用 `DataTable`/`SearchForm`。

### P2-4 前端错误被静默吞掉
- 证据：`TaskCenterView:304/429/470/513/607`、RequirementView 多处 `catch` 仅 `console.error`，用户看不到任何提示；同组件内 `loadTasks` 有 toast 而 `loadStats` 没有，体验不一致。
- 建议：建立统一错误边界 / toast，所有请求失败必须给用户可见反馈。

### P2-5 构建配置缺失分包
- 证据：`vite.config.js` 无 `manualChunks`；`MarkdownRender.vue:8` 顶层 `import mermaid` 被多个视图拉入；`RequirementGroupView:52` 静态 `import xlsx`。
- 建议：`build.rollupOptions.output.manualChunks` 拆 `element-plus/mermaid/xlsx/vue`；mermaid/xlsx 改动态 `import()`。

### P2-6 状态管理形同虚设 + 缺 composables
- 证据：`stores/index.js` 仅 `useAppStore`（title/collapsed）；"按姓名解析邮箱"在 3+ 视图重复调用，无缓存。
- 建议：引入 `composables/`（如 `useMail.ts`）承载可复用逻辑与缓存。

---

## 五、🟢 P3 — 工程化 / 卫生（低优，持续治理）

1. `requirements.txt` 用 `>=` 未锁版本 → 加 lock / 哈希提升可复现性。
2. 缺 `.gitattributes` → CRLF 抖动产生伪 diff；补上。
3. 身份文件 / `skills/` 未忽略、未提交 → 加入 `.gitignore`，避免误提交。
4. 缺统一日志规范（各模块 logger 命名不一）→ 统一 format/级别。
5. 纯 JS 无 TS → 规模已大，重构风险高；评估逐步引入 TS。
6. 运维脆弱：MySQL80 服务损坏、看门狗"自动拉起最新后端"但无受控停启 → 用 docker-compose 或带 healthcheck 的进程管理器。
7. 测试：后端 18 个 pytest 不错；**前端仅 2 个 vitest 规格、无 e2e**，新模块无测试 → 至少补任务中心/需求催办的冒烟测试。
8. `main.py:119` `Base.metadata.create_all` 与 Alembic 并存 → 仅保留 Alembic，避免漂移。

---

## 六、改进路线图（分阶段）

**阶段一 · 止血（本周，约 1-2 天）**
- [ ] 处理 P0-1：basic_data 要么原子提交，要么从 `main.py` 暂时摘掉
- [ ] 处理 P0-2：你本地重启后端，让需求催办修复生效
- [ ] 处理 P0-3：催办/逾期判据收敛为单一函数

**阶段二 · 架构加固（1-2 周）**
- [ ] P1-2：keywork 业务移入 service + 单事务回滚
- [ ] P1-4：邮件发信异步化 + 超时重试降级；通讯录批量解析
- [ ] P1-1：去掉弱默认密码，改强制环境变量
- [ ] P2-2 / P2-3 / P2-4：前端拆分 TaskCenterView + 抽 EmailComposeDialog/useMailCompose + 统一错误 toast
- [ ] P1-3：sent_emails.req_id 加索引、任务中心分页下沉 DB

**阶段三 · 工程化（持续）**
- [ ] P3：.gitattributes、锁版本、Docker/受控启停、前端测试、TS 评估、日志规范、统一异常信封

---

## 七、需要你拍板的三件事

1. **basic_data 怎么处理？** 它是其他会话的半成品，现在卡在工作区里。A：我帮你把它整套原子提交（连带迁移，安全）；B：在它做完前先从 `main.py` 摘掉，避免误提交崩后端。我倾向 **B（先摘掉保平安）**，等该模块做完再接回。
2. **邮件发信要不要异步化？** 这会改变"点发送立刻返回"的交互（改为后台发、结果回写）。对可靠性提升明显，建议做。
3. **任务中心是否要加缓存/快照？** 以当前数据量（几千条、单机单用户），**我的专业判断是不必**——实时聚合足够快，加缓存反而引入一致性复杂度。只需补索引 + DB 分页即可。

---

## 附：本次审查未改动任何代码，仅做静态分析与本地复核。
