"""业务领域聚合（kc-3 / P3）回归测试。

核心验证：领域浏览页「需求/运营/会议」卡片采用「源表归属 + 关联链接回溯」并集口径，
即使源记录自身 domain_code 为空（仅经 KnowledgeLinker 关联到该领域笔记），
也应通过 link 回溯纳入领域聚合，消除"时间线有、需求/运营空"的错位。
"""
from datetime import datetime

from db.models import (
    PmwbBusinessDomain,
    PmwbKnowledgeItem,
    PmwbKnowledgeLink,
    PmwbMeeting,
    PmwbOperationIssue,
    PmwbRequirementExt,
)
from services import business_domain
from services.knowledge_link_service import link_note


def _domain(db, code="ywt-broadband", name="一网通宽带", enabled=True):
    d = PmwbBusinessDomain(
        domain_code=code,
        domain_name=name,
        domain_group="商客业务",
        vault_path=f"01-业务知识/商客业务/{name}",
        enabled=enabled,
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


def _req(db, req_id, req_name):
    r = PmwbRequirementExt(req_id=req_id, req_name=req_name, status="proposed")
    db.add(r)
    db.commit()
    return r


def _issue(db, issue_no, title):
    i = PmwbOperationIssue(issue_no=issue_no, title=title, status="pending")
    db.add(i)
    db.commit()
    db.refresh(i)
    return i


def _meeting(db, meeting_id, title):
    m = PmwbMeeting(
        meeting_id=meeting_id,
        title=title,
        status="planned",
        start_time=datetime(2026, 1, 1, 10, 0),
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def _item(db, item_id, domain_code):
    it = PmwbKnowledgeItem(
        item_id=item_id,
        title=item_id,
        category="product",
        obsidian_path=f"/vault/{item_id}.md",
        domain_code=domain_code,
        source_type="manual",
        source_id=item_id,
    )
    db.add(it)
    db.commit()
    db.refresh(it)
    return it


def _link(db, item, source_type, source_id, domain_code):
    lk = PmwbKnowledgeLink(
        knowledge_item_id=item.id,
        source_type=source_type,
        source_id=str(source_id),
        domain_code=domain_code,
        link_type="main",
    )
    db.add(lk)
    db.commit()
    return lk


def test_get_related_union_requirement_via_link(db):
    _domain(db)
    # 需求自身 domain_code 为空，仅通过链接归属领域
    _req(db, "REQ-UNION-001", "联合归属需求")
    item = _item(db, "KN-U1", "ywt-broadband")
    _link(db, item, "requirement", "REQ-UNION-001", "ywt-broadband")

    out = business_domain.get_related(db, "ywt-broadband")
    assert "REQ-UNION-001" in [r.code for r in out.requirements]


def test_get_related_union_issue_via_link(db):
    _domain(db)
    issue = _issue(db, "ISSUE-U1", "运营问题")
    item = _item(db, "KN-U2", "ywt-broadband")
    _link(db, item, "operation", issue.id, "ywt-broadband")

    out = business_domain.get_related(db, "ywt-broadband")
    assert "ISSUE-U1" in [i.code for i in out.issues]


def test_get_related_union_meeting_via_link(db):
    _domain(db)
    meet = _meeting(db, "MEET-U1", "领域会议")
    item = _item(db, "KN-U3", "ywt-broadband")
    _link(db, item, "meeting", meet.id, "ywt-broadband")

    out = business_domain.get_related(db, "ywt-broadband")
    assert "MEET-U1" in [m.code for m in out.meetings]


def test_related_counts_union(db):
    _domain(db)
    _req(db, "REQ-CNT-001", "计数需求")
    item = _item(db, "KN-C1", "ywt-broadband")
    _link(db, item, "requirement", "REQ-CNT-001", "ywt-broadband")

    out = business_domain.list_all(db)
    dom = next(d for d in out if d.domain_code == "ywt-broadband")
    assert dom.req_count >= 1


def test_get_related_direct_domain_code_still_works(db):
    _domain(db)
    # 需求自身 domain_code 已设置，无链接也应纳入
    r = _req(db, "REQ-DIRECT-001", "直接归属需求")
    r.domain_code = "ywt-broadband"
    db.commit()
    out = business_domain.get_related(db, "ywt-broadband")
    assert "REQ-DIRECT-001" in [x.code for x in out.requirements]


def test_link_note_writeback_domain_code(db, monkeypatch):
    _domain(db)
    r = _req(db, "REQ-WB-001", "回填需求")
    item = _item(db, "KN-WB1", "ywt-broadband")
    # 屏蔽 vault frontmatter 同步，避免测试环境文件 IO
    monkeypatch.setattr(
        "services.knowledge_link_service._sync_frontmatter_and_section",
        lambda db, kid: None,
    )
    assert r.domain_code is None
    link_note(
        db,
        item.id,
        source_type="requirement",
        source_id="REQ-WB-001",
        link_type="main",
        domain_code="ywt-broadband",
    )
    db.refresh(r)
    assert r.domain_code == "ywt-broadband"
