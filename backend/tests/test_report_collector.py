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


def test_operation_issue_codes_translated_to_chinese(db):
    """运营工单的类别/状态/影响等级聚合键与高敏清单都必须转中文，禁止出现 prod/pending/P0 等内部码。"""
    from datetime import datetime
    from tests.factories import OperationIssueFactory
    today = date.today()
    OperationIssueFactory.create(
        db, title="高敏投诉工单", category="complaint", impact_level="P0",
        status="processing", handler="王五", discovery_date=datetime(today.year, today.month, today.day),
    )
    OperationIssueFactory.create(
        db, title="数据异常工单", category="data", impact_level="P2",
        status="resolved", handler="赵六", discovery_date=datetime(today.year, today.month, today.day),
    )
    data = ReportDataCollector(db).collect(today - timedelta(days=6), today)
    op = data["operation_issue"]
    assert "热点投诉" in op["by_category"]
    assert "数据异常管理" in op["by_category"]
    assert "处理中" in op["by_status"]
    assert "已解决" in op["by_status"]
    assert "致命(P0)" in op["by_impact"]
    # 高敏清单已转译具体标签
    hs = op["high_sensitivity"]
    assert any(h["category"] == "热点投诉" and h["impact"] == "致命(P0)" for h in hs)
    # 不得残留英文内部码
    assert not any("P0" in str(k) or "pending" in str(k) for k in op["by_status"])
    assert not any("prod" in str(k) or "complaint" in str(k) for k in op["by_category"])


def test_todo_and_devticket_codes_translated(db):
    """待办分类/优先级、开发工单状态聚合键转中文。"""
    from tests.factories import TodoFactory, RequirementExtFactory
    today = date.today()
    TodoFactory.create(db, title="待办T", category="requirement", priority="P1", status="todo",
                       due_date=today - timedelta(days=1))
    RequirementExtFactory.create(db, req_id="REQ-DV-1", status="dev", priority="P2", req_name="开发需求")
    data = ReportDataCollector(db).collect(today - timedelta(days=6), today)
    td = data["todo"]
    assert "需求" in td["by_category"]
    assert "严重(P1)" in td["by_priority"]
    # 开发工单状态（若有）转中文
    assert all(v not in ("created", "live") for v in data["dev_ticket"]["by_status"])


def test_po_risk_labels_translated(db):
    """PO 级风险需求的优先级/状态转中文标签。"""
    from tests.factories import RequirementExtFactory
    today = date.today()
    RequirementExtFactory.create(db, req_id="REQ-PO-1", status="dev", priority="P0", req_name="高风险需求")
    data = ReportDataCollector(db).collect(today - timedelta(days=6), today)
    po = data["requirement"]["po_risk"]
    assert any(p["req_name"] == "高风险需求" and p["status"] == "开发中" and p["priority"] == "最高(P0)" for p in po)


def test_meeting_action_unfinished_listed(db):
    """会议行动项采集应抛出未闭环清单（含标题/负责人/截止日），供下期计划逐条列出。"""
    from datetime import datetime
    from tests.factories import MeetingFactory
    today = date.today()
    m = MeetingFactory.create(db, meeting_id="M-UNF-1", start_time=datetime(today.year, today.month, today.day))
    MeetingFactory.add_action(db, meeting_id=m.id, content="跟进上线事项", owner="钱七")
    data = ReportDataCollector(db).collect(today - timedelta(days=6), today)
    ma = data["meeting_action"]
    assert ma["unfinished"]
    assert ma["unfinished"][0]["owner"] == "钱七"
    assert "跟进上线事项" in ma["unfinished"][0]["title"]


def test_todo_overdue_items_listed(db):
    """超期待办应进入 overdue_items 清单（含标题/截止日/分类），供下期计划逐条列出。"""
    from tests.factories import TodoFactory
    today = date.today()
    TodoFactory.create(db, title="超期待办A", category="requirement", priority="P0", status="todo",
                       due_date=today - timedelta(days=3))
    data = ReportDataCollector(db).collect(today - timedelta(days=6), today)
    td = data["todo"]
    assert td["overdue"] >= 1
    assert any(t["title"] == "超期待办A" for t in td["overdue_items"])
    assert td["overdue_items"][0]["category"] == "需求"


def test_next_period_section_lists_objects_not_just_numbers(db, monkeypatch):
    """下期计划段必须列出具体对象名（高敏工单/行动项/超期待办），而非只给数字。"""
    from datetime import datetime
    from tests.factories import OperationIssueFactory, MeetingFactory, TodoFactory
    from services import work_report as wr
    today = date.today()
    OperationIssueFactory.create(db, title="高敏X", category="bug", impact_level="P0",
                                 status="processing", handler="孙", discovery_date=datetime(today.year, today.month, today.day))
    m = MeetingFactory.create(db, meeting_id="M-NP-1", start_time=datetime(today.year, today.month, today.day))
    MeetingFactory.add_action(db, meeting_id=m.id, content="行动Y", owner="周")
    TodoFactory.create(db, title="超期Z", category="meeting", priority="P1", status="todo",
                       due_date=today - timedelta(days=2))
    start = today - timedelta(days=6)
    monkeypatch.setattr(wr, "generate_report_markdown", lambda db, s, u: ("", False, None, "no-llm"))
    result = wr.generate_report(db, {"report_type": "weekly", "date_start": start, "date_end": today})
    content = result["content"]
    assert "七、下周重点计划" in content
    # 具体对象名应出现（而非只报条数）
    assert "高敏X" in content
    assert "行动Y" in content
    assert "超期Z" in content


def test_prompt_includes_glossary():
    """提示词必须注入中文对照表，引导 LLM 转译内部编码。"""
    from services.report_prompt import build_system_prompt
    p = build_system_prompt("weekly")
    assert "内部编码→中文标签对照表" in p
    assert "热点投诉" in p
    assert "已上线" in p

