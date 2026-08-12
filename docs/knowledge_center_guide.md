# 知识中心使用规范（PMWB · kc-2 落地版）

> 本文档记录 kc-2 知识中心重构**实际落地**的设计与操作规范，供后续开发与使用参考。
> 合版提交：`ed00cffa`（2026-08-08，整批 kc-2 一次合入 main）。

## 1. 核心定位

以 Obsidian 原生笔记 + `pmwb_knowledge_item` 索引表 + `pmwb_knowledge_link` 关联表，把「业务对象（需求/工单/会议/运营）」与「业务知识笔记」打通：

- **领域基线**：每个二级业务领域（`pmwb_business_domain`）对应一组知识笔记。
- **需求 / 开发工单**：更新的知识，沉淀为独立笔记并关联领域。
- **运营工单 / 会议**：关联已有领域知识笔记（不重复造轮子），并进入领域「关联时间线」。

## 2. 数据模型

### pmwb_knowledge_item（知识索引）
字段：`id / item_id(唯一) / title / category / sub_category / tags / obsidian_path / source_type / source_id / domain_code / summary / 时间戳`。
- `source_type` ∈ `requirement / ticket / operation / meeting / manual / vault_sync`。
- `domain_code` 关联业务领域；是「按领域浏览」的主要维度。

### pmwb_knowledge_link（多对多关联）
字段：`id / knowledge_item_id / source_type / source_id / link_type / domain_code / note / 时间戳`。
- `source_type` ∈ `requirement / ticket / operation / meeting / deliverable / key_work`。
- `link_type` ∈ `main(主) / sub(子) / deliverable(交付物)`。
- 唯一约束 `(knowledge_item_id, source_type, source_id)`。

## 3. 关联方式（KnowledgeLinker）

前端组件 `frontend/src/components/Common/KnowledgeLinker.vue`，接入三个模块：
- `RequirementDeliveryView.vue`（需求详情）
- `WorkOrderView.vue`（运营工单详情）
- `MeetingView.vue`（会议详情）

接口（`backend/routers/knowledge.py`，**静态路径须注册在 `/{item_id}` 动态路由之前**）：
- `GET /knowledge/links?source_type=&source_id=` 查已关联笔记
- `POST /knowledge/links` 关联（body 含 knowledge_item_id / domain_code / link_type / note）
- `POST /knowledge/links/by-path` 按 Obsidian 路径关联
- `DELETE /knowledge/links/{link_id}` 取消关联

## 4. 沉淀入口（一键生成笔记）

`backend/services/obsidian_link.py`：
- `sediment_requirement(req_id, force)` —— 需求沉淀为知识条目；`force=True` 覆盖重生成。
- `sediment_user_story(story_id, force)` —— 用户故事业务规则沉淀为「业务规则」笔记并关联到所属需求。
- `sediment_meeting(meeting_id, force)` —— 会议纪要生成（五段式）；`force=True` 覆盖。
- `delete_meeting_minutes(meeting_id)` —— 删除纪要（清理 Obsidian 文件 + 索引 + 关联记录 + 反链）。
- `sediment_operation_issue` / `sediment_dev_ticket` —— 运营工单 / 开发工单沉淀。

落盘目录（与 Vault 真实结构一致）：
- 需求沉淀：`10-业务建设/需求沉淀`
- 业务规则：`10-业务建设/业务规则`
- 会议纪要：`05-会议纪要`
- 运营工单：`11-业务运营/{Bug解决方案|运营分析案例|运维SOP}`
- 开发交付：`14-知识沉淀/开发交付`

## 5. 按领域浏览

后端 `backend/services/business_domain.py:get_related(domain_code)` 聚合：
- `knowledge_items`：该领域全部知识条目（平铺，不区分主/子笔记）
- `requirements` / `meetings` / `issues`：关联的需求 / 会议 / 运营工单
- `timeline`：通过 `pmwb_knowledge_link` 建立的跨对象关联时间线

前端 `DomainKnowledgeView.vue`：领域卡片 → 详情弹窗（知识条目 / 需求 / 会议 / 运营工单 / 关联时间线 五个页签）。

## 6. ⚠️ 已知偏差（设计 vs 落地）

设计案（electric-vortex-lovelace.md v2.0）要求「每个二级领域一个业务知识**主笔记** + 子笔记分组（`note_type=business_main/sub_note`）」。

**实际未落地**：`PmwbKnowledgeItem` 模型**没有 `note_type` 列**，kc-2-1 迁移只包含关联表 + 运营 4 字段 + `manual_archived`。当前「按领域浏览」是平铺聚合 + 关联时间线，**无主/子笔记层级**。

> 若要补齐主笔记体系，需另开 S2 任务：给 `PmwbKnowledgeLink`/`PmwbKnowledgeItem` 增加 `note_type` 语义、重写 `get_related` 与 `DomainKnowledgeView`，并为每个二级领域生成主笔记。

## 7. 存量笔记迁移脚本

`backend/scripts/migrate_knowledge_frontmatter.py`（kc-2-6）：
- 为「已在 `pmwb_knowledge_item` 索引且带 `domain_code`」的笔记，补齐其 Obsidian 文件中缺失的 frontmatter：`domain_code / source_type / item_id`。
- 仅新增缺失字段，**不改已有值、不碰正文**；默认 `--dry-run` 出报告，`--fix` 才写回。
- 模型无 `note_type`，故不补该字段。

用法：
```bash
cd backend
./venv/Scripts/python.exe scripts/migrate_knowledge_frontmatter.py --dry-run   # 先审阅待变更清单
./venv/Scripts/python.exe scripts/migrate_knowledge_frontmatter.py --fix        # 经确认后写回
```
