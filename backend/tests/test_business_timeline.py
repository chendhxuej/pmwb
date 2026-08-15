# -*- coding: utf-8 -*-
"""kc4-3 业务全过程时间线测试：GET /api/v1/knowledge/business-timeline。

核心验收（对应 .workbuddy/tasks/kc4-3.md）：
- 选一业务，时间线返回该业务全部关联事件，按 event_date 倒序；
- 每条事件携带源记录标题 + 跳转路由 + 关联笔记路径（可双向跳转）；
- 支持按 event_type 过滤，且类型统计始终为全量口径（供筛选器展示）；
- 空业务返回空列表不报错。
"""
from datetime import date, datetime

import pytest

from core.config import settings
from db.models import (
    PmwbBusinessDomain,
    PmwbKnowledgeItem,
    PmwbKnowledgeLink,
    PmwbMeeting,
    PmwbOperationIssue,
    PmwbRequirementExt,
)
from services.knowledge_link_service import business_timeline


@pytest.fixture
def vault_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "OBSIDIAN_VAULT_PATH", str(tmp_path))
    return tmp_path


@pytest.fixture
def seeded(db):
    """造一个 ftto 业务：1 需求 + 1 会议 + 1 运营工单，各挂一条关联事件。"""
    db.add(
        PmwbBusinessDomain(
            domain_code="ftto",
            domain_name="FTTO",
            domain_group="政企",
            vault_path="01-业务知识/政企/FTTO",
            enabled=1,
        )
    )
    item = PmwbKnowledgeItem(
        item_id="KNOW-TL-001",
        title="FTTO",
        category="业务知识",
        domain_code="ftto",
        note_type="main",
        obsidian_path="01-业务知识/政企/FTTO/FTTO.md",
    )
    db.add(item)
    db.add(PmwbRequirementExt(req_id="REQ-TL-1", status="closed", domain_code="ftto", req_name="融合开通改造"))
    db.add(
        PmwbMeeting(
            meeting_id="MT-TL-1",
            title="FTTO 交付流程评审",
            meeting_type="review",
            domain_code="ftto",
            start_time=datetime(2026, 7, 20, 10, 0),
        )
    )
    db.add(
        PmwbOperationIssue(
            issue_no="OPS-TL-1",
            title="开通失败工单激增",
            domain_code="ftto",
            discovery_date=datetime(2026, 6, 15),
        )
    )
    db.commit()
    db.refresh(item)

    db.add_all(
        [
            PmwbKnowledgeLink(
                knowledge_item_id=item.id,
                source_type="requirement",
                source_id="REQ-TL-1",
                domain_code="ftto",
                link_type="auto",
                event_type="requirement",
                event_date=date(2026, 8, 1),
                summary="需求上线：融合开通改造",
            ),
            PmwbKnowledgeLink(
                knowledge_item_id=item.id,
                source_type="meeting",
                source_id="MT-TL-1",
                domain_code="ftto",
                link_type="auto",
                event_type="meeting",
                event_date=date(2026, 7, 20),
                summary="评审通过交付流程",
            ),
            PmwbKnowledgeLink(
                knowledge_item_id=item.id,
                source_type="operation",
                source_id="OPS-TL-1",
                domain_code="ftto",
                link_type="auto",
                event_type="operation",
                event_date=date(2026, 6, 15),
                summary="工单激增复盘",
            ),
        ]
    )
    db.commit()
    return item


def test_timeline_sorted_desc(client, db, seeded):
    """时间线按 event_date 倒序返回该业务全部事件。"""
    res = client.get("/api/v1/knowledge/business-timeline", params={"domain_code": "ftto"})
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["domain_code"] == "ftto"
    assert data["domain_name"] == "FTTO"
    assert data["total"] == 3
    dates = [e["event_date"] for e in data["events"]]
    assert dates == ["2026-08-01", "2026-07-20", "2026-06-15"]


def test_timeline_event_payload(client, db, seeded):
    """每条事件带中文类型、源记录标题、跳转路由、关联笔记路径。"""
    res = client.get("/api/v1/knowledge/business-timeline", params={"domain_code": "ftto"})
    events = {e["source_type"]: e for e in res.json()["data"]["events"]}

    req = events["requirement"]
    assert req["event_label"] == "需求"
    assert req["source_title"] == "融合开通改造"
    assert req["source_route"] == "/requirement-delivery"
    assert req["obsidian_path"].endswith("FTTO.md")
    assert req["knowledge_title"] == "FTTO"
    assert req["month"] == "2026-08"

    assert events["meeting"]["source_title"] == "FTTO 交付流程评审"
    assert events["meeting"]["source_route"] == "/meeting/list"
    assert events["operation"]["source_title"] == "开通失败工单激增"
    assert events["operation"]["source_route"] == "/operation/overview"


def test_timeline_type_filter_and_counts(client, db, seeded):
    """按类型过滤只返回该类型；类型统计仍是全量口径。"""
    res = client.get(
        "/api/v1/knowledge/business-timeline",
        params={"domain_code": "ftto", "event_type": "meeting"},
    )
    data = res.json()["data"]
    assert data["total"] == 1
    assert [e["event_type"] for e in data["events"]] == ["meeting"]
    # 筛选器统计仍看到 3 类
    assert {t["value"] for t in data["event_types"]} == {"requirement", "meeting", "operation"}
    assert all(t["count"] == 1 for t in data["event_types"])


def test_timeline_limit(client, db, seeded):
    """limit 截断但 total 反映全量。"""
    res = client.get(
        "/api/v1/knowledge/business-timeline", params={"domain_code": "ftto", "limit": 2}
    )
    data = res.json()["data"]
    assert data["total"] == 3
    assert data["returned"] == 2
    assert len(data["events"]) == 2


def test_timeline_empty_domain(client, db):
    """空业务返回空列表不报错。"""
    res = client.get(
        "/api/v1/knowledge/business-timeline", params={"domain_code": "not-exist"}
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["total"] == 0
    assert data["events"] == []
    assert data["event_types"] == []
    # 领域不存在时 domain_name 回落为 code，不抛异常
    assert data["domain_name"] == "not-exist"


def test_timeline_null_date_goes_last(client, db, seeded):
    """无 event_date 的历史关联垫底，不影响排序。"""
    item = seeded
    db.add(
        PmwbKnowledgeLink(
            knowledge_item_id=item.id,
            source_type="key_work",
            source_id="KW-OLD",
            domain_code="ftto",
            link_type="manual",
            event_type=None,
            event_date=None,
            note="历史遗留关联",
        )
    )
    db.commit()
    data = business_timeline(db, "ftto")
    assert data["total"] == 4
    last = data["events"][-1]
    assert last["source_id"] == "KW-OLD"
    assert last["event_date"] is None
    # event_type 缺失时回落 source_type
    assert last["event_type"] == "key_work"
    assert last["event_label"] == "重点工作"
    # summary 缺失时回落 note
    assert last["summary"] == "历史遗留关联"
