"""LLM 主导归类引擎测试（方案 v3.0，无关键词规则硬匹配）。

覆盖：
  1. 正常归类：高置信 → classify_by='ai'，低置信 → 'ai_low'，落 confidence/evidence
  2. 字典对齐：LLM 返回 l1 漂移时以字典归属为准；l2 编造 → 未分类+低置信
  3. LLM 不可用：工单保持待分析，不降级规则匹配
  4. 人工校正（manual）永不被覆盖，并作为 few-shot 回流
  5. 增量分析：已归类工单 force=False 不重跑
  6. JSON 容错解析（```json 包裹 / 噪音文本）
  7. 状态统计 classify_status / 端点
"""

from datetime import datetime

import pytest

from db.models import PmwbComplaintCategory, PmwbComplaintTicket
from services.complaint import llm_classify as lc
from services.complaint import config as C


# ─────────────────────────────────────────────────────────────
# 构造工具
# ─────────────────────────────────────────────────────────────
def _add(db, obj):
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def _seed_dict(db):
    """与线上 4 类体系一致的精简字典。"""
    for name, sort in (("系统问题", 10), ("流程优化", 20)):
        _add(db, PmwbComplaintCategory(level=1, name=name, sort_order=sort, enabled=1))
    _add(db, PmwbComplaintCategory(level=2, parent_name="系统问题",
                                   name="多出账与费用突增", sort_order=110, enabled=1))
    _add(db, PmwbComplaintCategory(level=2, parent_name="流程优化",
                                   name="施工单未触发", sort_order=210, enabled=1))


def _make_ticket(db, ticket_no="BOMC-001", **kw):
    defaults = dict(
        ticket_no=ticket_no, week="2026-W44", created_time=datetime(2026, 10, 26, 10, 0),
        city="苏州", content="10月出账比9月高40元，要求核实", status="已回复",
        category_l1="", category_l2="", classify_by="auto", dispatch_count=1,
    )
    defaults.update(kw)
    return _add(db, PmwbComplaintTicket(**defaults))


def _llm_payload(results):
    import json
    return {"used_llm": True, "text": json.dumps({"results": results}, ensure_ascii=False),
            "notice": ""}


@pytest.fixture()
def mocked_llm(monkeypatch):
    """替换 call_best_available，记录调用并返回预设响应列表（逐批弹出）。"""
    calls = []
    responses = []

    def _fake(db, system, user, max_tokens=None, timeout=None):
        calls.append({"system": system, "user": user})
        return responses.pop(0) if responses else {
            "used_llm": False, "text": "", "notice": "所有已启用的大模型均不可用"}

    monkeypatch.setattr(lc, "call_best_available", _fake)
    return calls, responses


# ─────────────────────────────────────────────────────────────
# 单元：解析与校验
# ─────────────────────────────────────────────────────────────
def test_extract_json_code_fence():
    raw = '```json\n{"results": [{"no": "A", "l1": "系统问题"}]}\n```'
    data = lc._extract_json(raw)
    assert data["results"][0]["no"] == "A"


def test_extract_json_with_noise():
    raw = '好的，以下是分析结果：\n{"results": [{"no": "A"}]}\n希望有帮助'
    assert lc._extract_json(raw)["results"][0]["no"] == "A"


def test_validate_l1_alignment_with_dict():
    l2_map = {"多出账与费用突增": "系统问题"}
    l1, l2, _ = lc._validate_result(
        {"l1": "流程优化", "l2": "多出账与费用突增", "confidence": 0.9}, l2_map, ["系统问题"])
    assert (l1, l2) == ("系统问题", "多出账与费用突增")


def test_validate_fabricated_l2_falls_unclassified():
    l1, l2, conf = lc._validate_result(
        {"l1": "瞎编类", "l2": "字典外场景", "confidence": 0.99}, {}, ["系统问题"])
    assert (l1, l2, conf) == (lc.UNCLASSIFIED, "", 0.0)


def test_validate_confidence_clamped():
    l1, l2, conf = lc._validate_result({"l1": "系统问题", "confidence": "abc"}, {}, ["系统问题"])
    assert conf == 0.0


# ─────────────────────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────────────────────
def test_run_classify_happy_path(db, mocked_llm):
    _seed_dict(db)
    t1 = _make_ticket(db, "BOMC-001")
    t2 = _make_ticket(db, "BOMC-002", content="融合开通提交后施工单一直未派发")
    calls, responses = mocked_llm
    responses.append(_llm_payload([
        {"no": "BOMC-001", "l1": "流程优化", "l2": "多出账与费用突增",
         "confidence": 0.92, "evidence": "处理过程核查为计费规则执行错误"},
        {"no": "BOMC-002", "l1": "流程优化", "l2": "施工单未触发",
         "confidence": 0.60, "evidence": "依据不足"},
    ]))
    res = lc.run_llm_classify(db)
    assert res["used_llm"] is True and res["updated"] == 2
    assert res["auto"] == 1 and res["low_conf"] == 1
    db.refresh(t1); db.refresh(t2)
    # t1：l1 以字典为准（LLM 说流程优化，字典归属系统问题）
    assert (t1.category_l1, t1.category_l2, t1.classify_by) == ("系统问题", "多出账与费用突增", C.LLM_CLASSIFY_BY)
    assert t1.ai_confidence == pytest.approx(0.92)
    assert "计费规则" in t1.ai_evidence
    # t2：低置信 → 人工确认队列
    assert t2.classify_by == C.LLM_LOW_CONF_BY


def test_llm_unavailable_keeps_pending(db, mocked_llm):
    _seed_dict(db)
    t = _make_ticket(db, "BOMC-001")
    res = lc.run_llm_classify(db)
    assert res["used_llm"] is False and res["updated"] == 0
    assert "不可用" in res["notice"]
    db.refresh(t)
    assert t.category_l1 == ""  # 保持待分析，绝不降级规则匹配
    assert t.ai_confidence is None


def test_manual_never_overwritten(db, mocked_llm):
    _seed_dict(db)
    _make_ticket(db, "BOMC-M", category_l1="数据问题", category_l2="实名与证件数据异常",
                 classify_by=C.CLASSIFY_MANUAL_BY)
    calls, responses = mocked_llm
    responses.append(_llm_payload([
        {"no": "BOMC-M", "l1": "系统问题", "l2": "多出账与费用突增",
         "confidence": 0.99, "evidence": "x"},
    ]))
    res = lc.run_llm_classify(db, force=True)
    assert res["scanned"] == 0  # manual 不进待分析
    row = db.query(PmwbComplaintTicket).filter_by(ticket_no="BOMC-M").first()
    assert (row.category_l1, row.classify_by) == ("数据问题", C.CLASSIFY_MANUAL_BY)


def test_incremental_skips_classified(db, mocked_llm):
    _seed_dict(db)
    _make_ticket(db, "BOMC-001", category_l1="系统问题", category_l2="多出账与费用突增",
                 classify_by=C.LLM_CLASSIFY_BY)
    _make_ticket(db, "BOMC-002")  # 待分析
    calls, responses = mocked_llm
    responses.append(_llm_payload([
        {"no": "BOMC-002", "l1": "系统问题", "l2": "多出账与费用突增",
         "confidence": 0.9, "evidence": "y"},
    ]))
    res = lc.run_llm_classify(db, force=False)
    assert res["scanned"] == 1
    # prompt 只含待分析工单，不含已归类工单
    assert "BOMC-002" in calls[0]["user"] and "BOMC-001" not in calls[0]["user"]


def test_few_shots_from_manual(db, mocked_llm):
    _seed_dict(db)
    _make_ticket(db, "BOMC-S", content="标准地址串号导致开通失败",
                 category_l1="数据问题", category_l2="标准地址错乱或串号",
                 classify_by=C.CLASSIFY_MANUAL_BY)
    _make_ticket(db, "BOMC-NEW")
    calls, responses = mocked_llm
    responses.append(_llm_payload([
        {"no": "BOMC-NEW", "l1": "系统问题", "l2": "多出账与费用突增",
         "confidence": 0.9, "evidence": "z"},
    ]))
    lc.run_llm_classify(db)
    assert "人工确认样例" in calls[0]["user"]
    assert "标准地址串号" in calls[0]["user"]  # few-shot 内容回流


def test_batch_split(db, mocked_llm, monkeypatch):
    _seed_dict(db)
    monkeypatch.setattr(C, "LLM_BATCH_SIZE", 2)
    for i in range(3):
        _make_ticket(db, f"BOMC-{i:03d}")
    calls, responses = mocked_llm
    responses.append(_llm_payload([
        {"no": "BOMC-000", "l1": "系统问题", "l2": "多出账与费用突增", "confidence": 0.9, "evidence": "1"},
        {"no": "BOMC-001", "l1": "系统问题", "l2": "多出账与费用突增", "confidence": 0.9, "evidence": "2"},
    ]))
    responses.append(_llm_payload([
        {"no": "BOMC-002", "l1": "系统问题", "l2": "多出账与费用突增", "confidence": 0.9, "evidence": "3"},
    ]))
    res = lc.run_llm_classify(db)
    assert len(calls) == 2  # 3 条按 2/批拆两批
    assert res["updated"] == 3


def test_classify_status_counts(db):
    _seed_dict(db)
    _make_ticket(db, "BOMC-A", category_l1="系统问题", classify_by=C.LLM_CLASSIFY_BY,
                 ai_confidence=0.9)
    _make_ticket(db, "BOMC-B", category_l1="系统问题", classify_by=C.LLM_LOW_CONF_BY, ai_confidence=0.5)
    _make_ticket(db, "BOMC-C", classify_by=C.CLASSIFY_MANUAL_BY, category_l1="数据问题")
    _make_ticket(db, "BOMC-D")  # 待分析
    st = lc.classify_status(db)
    assert st["total"] == 4 and st["ai"] == 1 and st["ai_low"] == 1
    assert st["manual"] == 1 and st["unclassified"] == 1
    assert st["rate"] == 75.0


# ─────────────────────────────────────────────────────────────
# API
# ─────────────────────────────────────────────────────────────
def test_api_classify_status(client, db):
    _seed_dict(db)
    _make_ticket(db, "BOMC-A", category_l1="系统问题", classify_by=C.LLM_CLASSIFY_BY)
    r = client.get("/api/v1/complaint/classify-status")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    assert body["data"]["ai"] == 1 and body["data"]["total"] == 1


def test_api_llm_classify_endpoint(client, db, mocked_llm):
    _seed_dict(db)
    _make_ticket(db, "BOMC-001")
    calls, responses = mocked_llm
    responses.append(_llm_payload([
        {"no": "BOMC-001", "l1": "系统问题", "l2": "多出账与费用突增",
         "confidence": 0.9, "evidence": "ok"},
    ]))
    r = client.post("/api/v1/complaint/llm-classify?force=false")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0 and body["data"]["updated"] == 1
