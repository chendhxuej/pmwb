"""T5 关联便捷性 — 批量设置业务领域（TDD 红→绿）。

验证 batch_set_domain：
1. 批量更新多条记录的 domain_code（录单即关联/批量修正）
2. overwrite=False 时跳过已有关联（不污染存量）
3. 未知 source_type / 不存在记录 计入 errors，不阻断其他
"""
import pytest

from db.models import PmwbKnowledgeItem
from services import business_domain as bd


def test_batch_set_domain_updates_note(db):
    db.add(PmwbKnowledgeItem(item_id="kn-b1", title="t", category="operation",
                              obsidian_path="x.md", domain_code=None))
    db.commit()
    res = bd.batch_set_domain(db, [{"source_type": "note", "source_id": "kn-b1", "domain_code": "ywt"}])
    assert res["updated"] == 1
    assert db.query(PmwbKnowledgeItem).filter_by(item_id="kn-b1").first().domain_code == "ywt"


def test_batch_set_domain_skip_nonempty(db):
    db.add(PmwbKnowledgeItem(item_id="kn-b2", title="t", category="operation",
                              obsidian_path="x.md", domain_code="old"))
    db.commit()
    res = bd.batch_set_domain(
        db, [{"source_type": "note", "source_id": "kn-b2", "domain_code": "new"}], overwrite=False
    )
    assert res["updated"] == 0 and res["skipped"] == 1
    assert db.query(PmwbKnowledgeItem).filter_by(item_id="kn-b2").first().domain_code == "old"


def test_batch_set_domain_unknown_and_notfound(db):
    res = bd.batch_set_domain(db, [
        {"source_type": "ghost", "source_id": "x", "domain_code": "ywt"},
        {"source_type": "note", "source_id": "nope", "domain_code": "ywt"},
    ])
    assert res["updated"] == 0
    assert len(res["errors"]) == 2
