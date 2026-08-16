"""report_collector 回归测试：重点锁定「完结需求工单（已上线 + delivered_date）识别」。"""
import pytest
from datetime import date, timedelta

from db.models import PmwbDevTicket, PmwbRequirementExt
from services.report_collector import ReportDataCollector


def _add_req(db, req_id, status="closed", delivered_date=None, **kwargs):
    obj = PmwbRequirementExt(
        req_id=req_id,
        status=status,
        req_name=kwargs.pop("req_name", req_id),
        delivered_date=delivered_date,
        **kwargs,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def _add_ticket(db, req_id, go_live_date=None, **kwargs):
    obj = PmwbDevTicket(
        ticket_no=f"TKT-{req_id}",
        req_id=req_id,
        system_name=kwargs.pop("system_name", "一网通"),
        go_live_date=go_live_date,
        **kwargs,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def test_delivered_items_recognizes_closed_requirement_with_delivered_date(db):
    """已上线(closed)且填了 delivered_date（本周），即便无开发工单，也应被识别进上线需求。"""
    today = date.today()
    _add_req(
        db, "REQ-DELIV-1", status="closed", delivered_date=today,
        req_name="完结需求A", system_name="一网通", sa_name="张三",
        description="实现 XX 功能，支撑融合开通",
    )
    start = today - timedelta(days=6)
    data = ReportDataCollector(db).collect(start, today)
    req = data["requirement"]
    assert "完结需求A" in req["buckets"]["delivered"]
    matched = [it for it in req["delivered_items"] if it["req_id"] == "REQ-DELIV-1"]
    assert matched, "delivered_items 中缺失完结需求工单（bug 复现）"
    it = matched[0]
    assert it["go_live"] == today.isoformat()
    assert it["delivered_date"] == today.isoformat()
    # 明细字段完整，供 LLM 逐条总结
    assert it["system_name"] == "一网通"
    assert it["sa_name"] == "张三"


def test_delivered_items_fallback_to_dev_ticket_go_live(db):
    """兼容旧口径：无 delivered_date，但开发工单 go_live_date 在本周，仍应识别。"""
    today = date.today()
    _add_req(db, "REQ-NODELIV-1", status="closed", req_name="工单上线需求B")
    _add_ticket(db, "REQ-NODELIV-1", go_live_date=today)
    start = today - timedelta(days=6)
    data = ReportDataCollector(db).collect(start, today)
    req = data["requirement"]
    assert "工单上线需求B" in req["buckets"]["delivered"]
    matched = [it for it in req["delivered_items"] if it["req_id"] == "REQ-NODELIV-1"]
    assert matched
    assert matched[0]["go_live"] == today.isoformat()


def test_delivered_date_out_of_range_not_counted_this_week(db):
    """已上线但 delivered_date 在上周（区间外），本周报告不应计入上线需求。"""
    today = date.today()
    last_week = today - timedelta(days=10)
    _add_req(db, "REQ-OLD-1", status="closed", delivered_date=last_week, req_name="上周上线需求C")
    start = today - timedelta(days=6)
    data = ReportDataCollector(db).collect(start, today)
    req = data["requirement"]
    assert "上周上线需求C" not in req["buckets"]["delivered"]
    assert not [it for it in req["delivered_items"] if it["req_id"] == "REQ-OLD-1"]


def test_no_name_error_on_delivered_branch(db):
    """delivered 分支不得再引用未定义变量 item（此前会 NameError 崩溃）。"""
    today = date.today()
    _add_req(db, "REQ-X-1", status="closed", delivered_date=today, req_name="X需求")
    _add_req(db, "REQ-X-2", status="dev", req_name="Y进行中")
    start = today - timedelta(days=6)
    # 不应抛出异常
    data = ReportDataCollector(db).collect(start, today)
    assert isinstance(data["requirement"]["delivered_items"], list)


def test_generate_report_includes_delivered_requirement_in_markdown(db, monkeypatch):
    """端到端：完结需求工单应写入周报正文（规则模板兜底的「完成【需求名】开发部署」句式）。"""
    today = date.today()
    _add_req(
        db, "REQ-GEN-1", status="closed", delivered_date=today,
        req_name="生成验证需求", system_name="一网通", sa_name="李四",
        description="核心功能实现",
    )
    start = today - timedelta(days=6)
    from services import work_report as wr

    # 强制走规则模板兜底（不调真实 LLM），验证数据落文
    monkeypatch.setattr(wr, "generate_report_markdown", lambda db, s, u: ("", False, None, "no-llm"))
    result = wr.generate_report(db, {"report_type": "weekly", "date_start": start, "date_end": today})
    assert "生成验证需求" in result["content"]
    assert "完成【生成验证需求】开发部署" in result["content"]
