# -*- coding: utf-8 -*-
"""kc4-2 主笔记自动区回流引擎测试：sync_main_note_from_links。

核心验收（对应 .workbuddy/tasks/kc4-2.md）：
- 已关闭 + 勾选 product_changed 的需求 → 回写「产商品」自动区；
- 未勾变更标记 / 未关闭的需求 → 不污染产商品与业务流程自动区；
- 用户故事 rules 非空 → 回写「场景规则」自动区；
- 全部关联事件 → 回写「业务时间线」自动区（按日期倒序）；
- **人工区（业务概述 / 通用规则 / 资费 / 关联系统）零覆盖**——这是最关键的安全断言；
- 幂等：重复同步不重复追加内容。
"""
import os
from datetime import date

import pytest

from core.config import settings
from db.models import (
    PmwbKnowledgeItem,
    PmwbKnowledgeLink,
    PmwbRequirementExt,
    PmwbUserStory,
)
from services.knowledge_link_service import sync_main_note_from_links


@pytest.fixture
def vault_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "OBSIDIAN_VAULT_PATH", str(tmp_path))
    return tmp_path


def _create_domain(client, code="ftto", name="FTTO"):
    res = client.post(
        "/api/v1/basic-data/business-domains",
        json={
            "domain_code": code,
            "domain_name": name,
            "domain_group": "政企",
            "vault_path": f"01-业务知识/政企/{name}",
            "match_keywords": name,
            "enabled": 1,
        },
    )
    assert res.status_code == 200, res.text
    return res.json()["data"]


def _main_note(client, code="ftto"):
    res = client.post("/api/v1/knowledge/main-note", json={"domain_code": code})
    assert res.status_code == 200, res.text
    return res.json()["data"]["item"]


def _read(vault, rel_path):
    return open(os.path.join(str(vault), rel_path), encoding="utf-8").read()


def _add_req(db, req_id, status, product_changed=0, process_changed=0, name=None):
    req = PmwbRequirementExt(
        req_id=req_id,
        status=status,
        domain_code="ftto",
        req_name=name or f"{req_id} 需求",
        description=f"{req_id} 的变更说明",
        system_name="CRM",
        product_changed=product_changed,
        process_changed=process_changed,
        version_required_date=date(2026, 8, 1),
    )
    db.add(req)
    db.commit()
    return req


def test_template_contains_auto_blocks(client, vault_tmp):
    """主笔记模板须预置自动区标记块，且人工区章节保留。"""
    _create_domain(client)
    item = _main_note(client)
    content = _read(vault_tmp, item["obsidian_path"])
    for key in ("product", "process", "scenario_rules", "change_log", "deliverables", "timeline"):
        assert f"<!-- PMWB:AUTO:BEGIN key={key} -->" in content, key
        assert f"<!-- PMWB:AUTO:END key={key} -->" in content, key
    # 人工区章节存在
    assert "## 1. 业务概述" in content
    assert "### 4.1 通用规则（人工维护）" in content
    assert "## 9. 业务全过程时间线" in content


def test_sync_writes_product_only_for_closed_flagged(client, db, vault_tmp):
    """核心分级策略：仅「已关闭 + 勾选产商品变更」的需求才进产商品自动区。"""
    _create_domain(client)
    item = _main_note(client)

    _add_req(db, "REQ-CLOSED-FLAG", "closed", product_changed=1, name="已关闭且标记产商品")
    _add_req(db, "REQ-CLOSED-NOFLAG", "closed", name="已关闭未标记")
    _add_req(db, "REQ-DEV-FLAG", "dev", product_changed=1, name="开发中已标记")

    result = sync_main_note_from_links(db, "ftto")
    assert result["changed"] is True
    assert "product" in result["blocks_written"]

    content = _read(vault_tmp, item["obsidian_path"])
    assert "REQ-CLOSED-FLAG" in content
    # 未勾标记、未关闭的需求不得进入产商品区
    product_block = content.split("key=product -->")[1].split("<!-- PMWB:AUTO:END key=product")[0]
    assert "REQ-CLOSED-NOFLAG" not in product_block
    assert "REQ-DEV-FLAG" not in product_block


def test_sync_process_and_change_log(client, db, vault_tmp):
    """流程变更标记进业务流程区；变更轨迹汇总带标记的已关闭需求。"""
    _create_domain(client)
    item = _main_note(client)
    _add_req(db, "REQ-PROC", "closed", process_changed=1, name="流程优化需求")

    sync_main_note_from_links(db, "ftto")
    content = _read(vault_tmp, item["obsidian_path"])

    process_block = content.split("key=process -->")[1].split("<!-- PMWB:AUTO:END key=process")[0]
    assert "REQ-PROC" in process_block
    change_block = content.split("key=change_log -->")[1].split("<!-- PMWB:AUTO:END key=change_log")[0]
    assert "REQ-PROC" in change_block
    assert "业务流程" in change_block


def test_sync_scenario_rules_from_user_story(client, db, vault_tmp):
    """用户故事 rules 非空即回写场景规则区（结构化、可追溯，风险低）。"""
    _create_domain(client)
    item = _main_note(client)
    _add_req(db, "REQ-RULE", "dev", name="带规则需求")
    db.add(
        PmwbUserStory(
            req_id="REQ-RULE",
            seq=1,
            title="下单校验",
            rules='["同一客户同月仅可办理一次", "欠费客户不允许新装"]',
        )
    )
    db.commit()

    sync_main_note_from_links(db, "ftto")
    content = _read(vault_tmp, item["obsidian_path"])
    rules_block = content.split("key=scenario_rules -->")[1].split(
        "<!-- PMWB:AUTO:END key=scenario_rules"
    )[0]
    assert "同一客户同月仅可办理一次" in rules_block
    assert "欠费客户不允许新装" in rules_block


def test_sync_timeline_desc_order(client, db, vault_tmp):
    """业务时间线按 event_date 倒序，覆盖多类型事件。"""
    _create_domain(client)
    item = _main_note(client)
    db.add_all(
        [
            PmwbKnowledgeLink(
                knowledge_item_id=item["id"],
                source_type="requirement",
                source_id="REQ-OLD",
                link_type="main",
                domain_code="ftto",
                event_type="requirement",
                event_date=date(2026, 1, 5),
                summary="旧需求上线",
            ),
            PmwbKnowledgeLink(
                knowledge_item_id=item["id"],
                source_type="meeting",
                source_id="MTG-NEW",
                link_type="sub",
                domain_code="ftto",
                event_type="meeting",
                event_date=date(2026, 8, 10),
                summary="需求评审会",
            ),
        ]
    )
    db.commit()

    sync_main_note_from_links(db, "ftto")
    content = _read(vault_tmp, item["obsidian_path"])
    tl = content.split("key=timeline -->")[1].split("<!-- PMWB:AUTO:END key=timeline")[0]
    assert "MTG-NEW" in tl and "REQ-OLD" in tl
    # 倒序：新事件在前
    assert tl.index("MTG-NEW") < tl.index("REQ-OLD")
    assert "需求评审会" in tl


def test_manual_region_never_overwritten(client, db, vault_tmp):
    """最关键安全断言：人工手写内容在多次同步后必须原样保留。"""
    _create_domain(client)
    item = _main_note(client)
    path = os.path.join(str(vault_tmp), item["obsidian_path"])

    # 模拟老大手写人工区内容
    content = open(path, encoding="utf-8").read()
    content = content.replace(
        "- **业务定义**：", "- **业务定义**：面向小微企业的光纤到办公室接入产品（人工撰写勿删）"
    )
    content = content.replace(
        "### 4.1 通用规则（人工维护）\n\n- ",
        "### 4.1 通用规则（人工维护）\n\n- 人工规则：所有变更需经产品经理确认",
    )
    open(path, "w", encoding="utf-8").write(content)

    _add_req(db, "REQ-X", "closed", product_changed=1)
    sync_main_note_from_links(db, "ftto")
    sync_main_note_from_links(db, "ftto")  # 幂等：连续两次

    after = open(path, encoding="utf-8").read()
    assert "面向小微企业的光纤到办公室接入产品（人工撰写勿删）" in after
    assert "人工规则：所有变更需经产品经理确认" in after
    # 自动区已写入
    assert "REQ-X" in after
    # 幂等：自动区标记不重复
    assert after.count("<!-- PMWB:AUTO:BEGIN key=product -->") == 1
    assert after.count("<!-- PMWB:AUTO:BEGIN key=timeline -->") == 1


def test_sync_endpoint(client, db, vault_tmp):
    """POST /knowledge/sync-main-note 端点可用。"""
    _create_domain(client)
    _main_note(client)
    _add_req(db, "REQ-EP", "closed", product_changed=1)
    res = client.post("/api/v1/knowledge/sync-main-note", json={"domain_code": "ftto"})
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["domain_code"] == "ftto"
    assert data["changed"] is True
    assert "product" in data["blocks_written"]


def test_sync_empty_domain_no_error(client, db, vault_tmp):
    """空业务（无需求无关联）同步不报错，自动区显示占位文案。"""
    _create_domain(client, code="empty-biz", name="空业务")
    item = _main_note(client, code="empty-biz")
    result = sync_main_note_from_links(db, "empty-biz")
    assert result["main_note_path"]
    content = _read(vault_tmp, item["obsidian_path"])
    assert "_暂无关联事件_" in content
