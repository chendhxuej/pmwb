# 知识中心详细实施方案 · feature/kc4-knowledge-hub（S1 方案门禁交付物）

> 关联文档：`docs/knowledge_center_redesign_v2.md`（设计基线 + 已落地决策）。
> 本文为 S1 详细技术方案，供老大门禁确认后进入开发（走 feature 分支）。

## 0. 目标与范围（源自 v2.1 决策）

把知识中心从"5 个脱节 Tab"收敛为"以 Obsidian 业务笔记为底座、以业务为中心"的 3 视图体系，并补齐两处真正缺口：

1. **主笔记自动区回流**（sync_main_note）——让需求/规则/交付物自动回填主笔记，从业务看全貌。
2. **业务时间线**（business-timeline）——从关联表反向看某业务各时间点干了什么。
3. **交付物去开发工单化**——操作手册等文件以需求为直接源归档。
4. **SQL脚本库保留并补 domain_code**——纳入领域体系与知识检索。
5. **开发工单彻底退出**——后端 `pmwb_dev_ticket`/`sediment_dev_ticket` 标记废弃，数据保留。

不在本期：半自动速记向导 UI（P2）、需求/会议/工单的自动触发钩子（P2，仅先做按需/手动入口）。

---

## 1. 数据模型改造（Alembic 迁移）

> 惯例：新建迁移前 `alembic heads` 查当前最大号，`down_revision` 指向实际 head，避免修订号冲突。

### 1.1 `pmwb_knowledge_link` 扩字段（向后兼容）
```python
event_type   = Column(String(64), comment="时间线事件类型，默认=source_type：requirement/operation/meeting/delivery/rule/manual")
event_date   = Column(Date, comment="过程事件发生日（需求关闭日/会议日/工单完成日），时间线主键；旧数据回填为 created_at 日期")
summary      = Column(String(500), comment="一句话摘要，时间线叙事用")
```
- 索引：`idx_kl_event_date`(event_date)；`idx_kl_event_type`(event_type)。
- 迁移中对**存量数据**回填：`event_type = source_type`，`event_date = DATE(created_at)`。

### 1.2 `pmwb_requirement_ext` 增变更标记
```python
product_changed  = Column(Integer, default=0, comment="本需求是否涉及产商品体系变更（1是），用于主笔记§2保守回写")
process_changed   = Column(Integer, default=0, comment="本需求是否涉及业务流程变更（1是），用于主笔记§3保守回写")
```
- 在需求定稿/关闭界面由产品经理勾选（前端增加两个开关）。

### 1.3 `pmwb_sql_script` 增 domain_code
```python
domain_code = Column(String(64), comment="关联业务领域编码，纳入领域体系与知识检索")
```
- 索引 `idx_sql_domain`(domain_code)；原 `category`（自由业务线）保留作二级分类。
- 存量脚本 domain_code 为空，前端提供"批量按业务线映射 domain"工具或逐条补。

### 1.4 需求交付物（去开发工单）
现状：`archive_requirement_manual` 读"需求关联开发工单"文件。开发工单废弃后，需**需求直接挂载文件**。
- 复用/确认现有 `pmwb_requirement_ext.deliverables` 关系目标模型（实现时 grep 确认类名，缺则新增 `PmwbRequirementDeliverable`：`req_id/file_name/file_path/file_type/domain_code`）。
- 归档时读需求自身交付物文件 → 复制到 `06-交付物/attachments/` → 登记主笔记 §6 + link（event_type=delivery）。

---

## 2. 服务层改造

### 2.1 `sync_main_note_from_links(domain_code)`（核心新增）
位置：`services/knowledge_link_service.py`（沿用既有主笔记构建逻辑）。

逻辑：
1. `ensure_domain_main_note(domain_code)` 保活主笔记骨架；
2. 查 `pmwb_knowledge_link`（domain_code + 各 source）及其指向的子笔记 frontmatter；
3. **分级回写自动区**（严格按 v2.1 §10 决策）：
   - §2 产商品：仅 `PmwbRequirementExt.status=='closed' AND product_changed==1` 的需求，且其用户故事/交付物含产商品信息；
   - §3 业务流程：仅 `status=='closed' AND process_changed==1`；
   - §4.1 场景规则：用户故事 `rules` 非空即追加（按 `### REQ-xxx` 分段，幂等）；
   - §6 交付物：需求交付物文件列表；
   - §8 业务时间线：遍历全部 link，按 `event_date` 倒序生成（含 summary）；
   - §9 反向链接：backlinks 聚合。
4. **绝不改写** §1 概述 / §4.2 通用规则 / §7 关联系统（人工区）。
5. 写入主笔记 Markdown 文件 + 更新 `auto_sections_generated_at` frontmatter。

### 2.2 `business_timeline(domain_code, from_, to_)`
位置：`services/knowledge_link_service.py` 或新 `services/business_timeline.py`。
- 查 link 表 → 关联源记录取 `event_date`/`summary`/`source_type`/`source_id`/note_path → 按日分组返回 `{date, events:[{type,title,summary,path}]}`。
- 支持 `from`/`to` 区间过滤。

### 2.3 `archive_requirement_manual` 改造
- 入参不变（`req_id`），内部改为读**需求交付物文件**（§1.4）而非开发工单；
- 落 `06-交付物/attachments/` + 登记主笔记 §6 + link(event_type=delivery, event_date=归档日)。

### 2.4 沉淀触发（本期做入口，钩子留 P2）
- 保留现有按需端点：`/sediment/requirement/{id}`、`/sediment/requirement/{id}/rules`、`/sediment/operation/{id}/rules`、会议沉淀。
- 新增 `/sediment/requirement/{id}/delivery`（需求文件归档）。
- 各 sediment 完成后**自动调用** `sync_main_note_from_links(domain_code)` 回流主笔记（半自动闭环，无需手动再点同步）。

---

## 3. 接口设计

新增（均在 `routers/knowledge.py`，prefix `/api/v1/knowledge`）：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/business-timeline?domain_code=&from=&to=` | 业务时间线事件序列 |
| POST | `/sync-main-note` | payload `{domain_code}`，触发主笔记自动区回流 |
| POST | `/sediment/requirement/{req_id}/delivery` | 需求交付物归档（去开发工单） |

改造：
- `POST /sediment/requirement/{req_id}` 等 sediment 端点：成功后内部自动 `sync_main_note_from_links`。
- SQL脚本 CRUD（`routers/sql_script.py` 或现有）：create/update 接收 `domain_code`；列表/检索支持 `domain_code` 过滤（纳入知识检索）。
- 开发工单相关端点：`/dev-tickets/*` 与 `obsidian.py` 的 `sediment_dev_ticket` 标记 `@deprecated`，路由保留但文档注明退出知识沉淀链路（数据不删）。

---

## 4. 前端（3 视图收敛）

`KnowledgeCenterView.vue` 的 5 Tab 重构为 3 视图（保留组件复用，避免白屏）：

### 4.1 业务全景 HUB（核心，替换"按领域浏览"+吸收"产品圣经"）
- 左：领域树（消费 `pmwb_business_domain`）。
- 右：主笔记渲染（obsidian markdown 渲染组件，沿用现有）+ **业务时间线组件**（调用 `/business-timeline`，时间轴样式）。
- 产品圣经：不再读 `PRODUCT_BIBLE` 硬编码，改为"主笔记 §2 产商品体系"的卡片化呈现；`PRODUCT_BIBLE` 配置项标记废弃。
- 顶部操作：`同步主笔记`（调 `/sync-main-note`）、`沉淀此业务`（速记入口）。

### 4.2 知识检索（吸收"知识库"Tab）
- 跨领域全文 + 类型/标签/domain/时间过滤（复用 `/knowledge?domain_code=&...`）。
- 结果项可跳主笔记或原子笔记详情。
- SQL脚本库作为 `source_type=sql_script`（带 domain_code）纳入检索结果。

### 4.3 沉淀向导（替换错配的"知识沉淀"Tab）
- 速记收件箱 + 一键沉淀（选 domain + type → 调对应 sediment）。
- 需求交付物归档按钮（调 `/sediment/requirement/{id}/delivery`）。
- SQL脚本库：保留在此视图的"资源"区，提供 domain_code 选择/批量映射。

---

## 5. 实施步骤（feature 分支拆分）

按"小步自测、每步可验证"拆分（均基于 `feature/kc4-knowledge-hub` 或再细分子分支）：

| 子任务 | 内容 | 验收 |
|--------|------|------|
| kc4-1 link 扩展 | 迁移加 event_type/event_date/summary + 存量回填 | alembic upgrade 通过；旧 link 有 event_date |
| kc4-2 主笔记回流 | `sync_main_note_from_links` + 分级回写 + 自动触发 | 闭合需求后主笔记 §2/§4.1/§6/§8 自动刷新；人工区不变 |
| kc4-3 时间线 | `business_timeline` 接口 + 前端时间线组件 | 选业务显示按时间排序的事件流 |
| kc4-4 交付物去开发工单 | 需求交付物模型/挂载 + archive 改造 + 新端点 | 需求直挂文件 → 归档到 06 + 主笔记 §6 |
| kc4-5 SQL domain | `pmwb_sql_script.domain_code` 迁移 + CRUD 改造 + 检索纳入 | SQL脚本可标 domain，检索可过滤 |
| kc4-6 UI 三视图 | HUB/检索/沉淀向导 重构 + 产品圣经去硬编码 | 3 视图可用，无白屏，构建干净 |

---

## 6. 测试与验收

- 后端 pytest：link 扩展迁移、sync_main_note 分级回写（mock 需求 closed+product_changed）、business_timeline 排序、delivery 去开发工单归档。
- 前端 vitest + `npm run build` 干净；**无头浏览器冒烟**：3 视图路由可达、时间线组件渲染、同步按钮生效（防白屏，验证图标 import）。
- 端到端手测：选一业务 → 关闭一需求(勾 product_changed) → 点同步 → 主笔记 §2/§8 出现该需求；时间线含该事件。

---

## 7. 风险与约定

- **人工区零覆盖**：sync 只写自动区，重算即刷新；任何 PR 不得改 §1/§4.2/§7。
- **开发工单数据不删**：仅退出链路，路由保留 deprecated，避免破坏既有引用。
- **迁移修订号**：先 `alembic heads` 取最大号+1，勿用已占用号（如 `20260804000001`）。
- **时区**：event_date 用业务日期（naive date），展示层 ±8h 规则不变。

---

## 8. 待老大门禁确认

1. 需求"产商品/流程变更标记"采用新增 `product_changed`/`process_changed` 布尔字段（默认 0，关闭时勾选），认可？
2. 需求交付物采用"需求直接挂载文件 + 新增/复用交付物表"方式，认可（不再经开发工单）？
3. 半自动速记向导 UI 与自动触发钩子按 P2 延后，本期只做按需/手动入口，认可？
4. 确认后我走 `feature/kc4-knowledge-hub` 分支，按 kc4-1~6 顺序开发，每步自测。
