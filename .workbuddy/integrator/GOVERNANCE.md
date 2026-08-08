# 多 AI 共享工作树管控机制（方案二：Vicky2号 单一集成者）

> 本机制在《COLLABORATIVE_DEV_WORKFLOW.md》角色分工之上，**专治「多 AI 共用一份工作树 + 沙箱自动切分支导致文件丢失/互相覆盖」**。
> 所有 AI（含开发者 AI）**启动时必须先读本文件 + OWNERSHIP.md**，违反即视为事故。
> 生效时间：2026-08-08，由老大拍板采用方案二。

---

## 一、角色与权限边界（硬规则）

| 角色 | 权限 | 禁止 |
|---|---|---|
| **集成者（Vicky2号）** | 唯一可执行 `git commit`/`git push`/`git merge`/`git checkout`/`git switch`/`git reset`；负责把各 AI 成果安全入库 | 无 |
| **开发者 AI（晓伴等）** | 仅编辑 OWNERSHIP.md 中**自己名下**的文件；`git status`/`git diff` 只读 | **禁止** `git commit`/`push`/`merge`/`checkout`/`switch`/`reset --hard`/`clean`/`stash -u`（这些会切分支或删未跟踪文件，是 AI总结 丢失事故的元凶） |

**唯一切分支例外**：开发者 AI 在「新建自己任务分支」时，可向集成者申领分支名后执行**一次** `git checkout -b feature/<分配名>`，之后**不得再切走**，全程待在该分支工作树内。

---

## 二、分支与文件归属

1. **分支命名**由集成者统一分配：`feature/<模块>-<序号>-<简短描述>`，避免撞名。
2. **OWNERSHIP.md（文件/目录归属表）** 是编辑前的必查清单：改任何文件前先查它是否属于自己；**不是自己名下的文件一律不动**，需改动必须先往 INTEGRATION_QUEUE.md 提「协调申请」，由集成者仲裁。
3. 当前已知归属（详见 OWNERSHIP.md）：
   - AI总结 / WorkReport 模块 → **Vicky2号** 直管（已被切分支搞丢过，敏感）
   - sup-3 监督/工单模块 → 对应开发者 AI
   - 已合入 main 的既有模块（mc/tc/ma/umc/db…）→ **锁定**，非领新任务不得改

---

## 三、防「切分支导致文件丢失」三道防线

1. **出站备份（强制，每个 AI 每次收工前必做）**
   - 把本分支未跟踪/未提交的成果复制到仓库外 `D:/项目/_<branch>_backup/`（WorkReport 已示范：`D:/项目/_wr_backup/work-report/`）。
   - 集成者定期按备份 reconcile 回正确分支，不依赖 git 分支状态。

2. **Checkout 锁 CHECKOUT_LOCK**
   - 记录「当前 checkout 分支 + 持有人 + 时间戳」。沙箱若自动切走，本锁仅作记录；**真正防线是上面的备份 + 集成者还原**。

3. **以工作树为准的入库法（应对 git 对象库损坏）**
   - 入库**不依赖 `git merge`**。改用：工作目录为准 → `git read-tree origin/main` 重建索引 → `git add -A` **仅加本任务文件** → commit → fast-forward push（详见 MEMORY.md「沙箱 git 仓库残缺+对象库损坏坑」）。
   - 仅集成者可执行。

---

## 四、成果交接协议（Handoff）

开发者 AI 完成自测后：

1. 在 `.workbuddy/integrator/handoff/<branch>.md` 写**结构化交接单**（模板见 `handoff/_TEMPLATE.md`），必须含：
   - 分支名 / 任务号 / 负责人 AI
   - 改动文件清单（绝对路径）
   - 涉及的**接线点**（建表/ALTER、`main.py` 注册、`router` 菜单等）
   - **自测结果（必须含真实访问验证，如 HTTP 状态码 / 页面渲染）**
   - 「可否入库：是/否」+ 备注
2. 把任务号追加进 `INTEGRATION_QUEUE.md` 队列。

**集成者按队列 FIFO 处理**：代码门禁审查 → 从备份/工作树还原 → 提交到正确分支 → 标记 `[done]`。

---

## 五、冲突仲裁

- **两 AI 改同一文件**：以 OWNERSHIP.md 主人为准；无主文件由集成者裁定归属，另一方改为在自己分支实现或提协调申请。
- **某分支被沙箱切丢文件**：集成者从对应 `D:/项目/_<branch>_backup/` 还原，**不靠 git**。

---

## 六、当前落地待办（集成者执行）

1. 把 AI总结 模块从「sup-3 上的未跟踪文件」迁到正式 `feature/ai-report` 分支并入库（备份 `D:/项目/_wr_backup/work-report/` 已就绪）。
2. 维护 OWNERSHIP.md / INTEGRATION_QUEUE.md，确保每个活跃分支有归属、有队列记录。
3. 其他 AI 每轮收工按第三节第 1 条备份，并在 handoff/ 留交接单。

> 本机制不取代既有质量门禁（pytest/vitest/build/冒烟/审查），仅叠加「共享树安全」层。
