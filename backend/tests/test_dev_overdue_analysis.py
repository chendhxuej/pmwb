"""需求开发超期专题分析（AI总结固化专题）单测 —— 2026-10-19。

锁定口径（改这几条等于改业务定义，须老大确认）：
1. 对象 = `status='dev'`（开发中）且**尚未上线**（delivered_date 与开发工单 go_live_date 均为空）；
2. 计时起点 = `stage='dev'` 的 `entered_at`（进入「启动开发」），与工作量分析同源；
3. 超期 = 基准日 − 启动开发日 **严格大于** 阈值，默认 25 天，生成时可手工改；
4. 明细表/统计由确定性渲染，LLM 只写「研判与建议」。

安全：不涉邮件发送，不写 MySQL（内存 SQLite）。
"""
from datetime import date, datetime, timedelta

import services.work_report as wr
import services.requirement_dev_overdue as rdo
from db.models import (
    PmwbDevTicket,
    PmwbReqVendorDev,
    PmwbRequirementEvaluation,
    PmwbRequirementExt,
    PmwbRequirementStageLog,
)

AS_OF = date(2026, 10, 19)


# ────────────────────────── 造数 helpers ──────────────────────────
def add_req(db, req_id, status="dev", name=None, priority="P2", system="CRM",
            sa="吴雨霜", delivered=None, version_req=None):
    db.add(PmwbRequirementExt(
        req_id=req_id, status=status, req_name=name or f"需求{req_id}",
        priority=priority, system_name=system, sa_name=sa,
        delivered_date=delivered, version_required_date=version_req,
    ))
    db.commit()


def add_dev(db, req_id, days_ago, source="auto"):
    when = datetime.combine(AS_OF - timedelta(days=days_ago), datetime.min.time()) + timedelta(hours=10)
    db.add(PmwbRequirementStageLog(req_id=req_id, stage="dev", entered_at=when, source=source))
    db.commit()


def add_eval(db, req_id, sa="吴雨霜", system="CRM", workload=None, review=None):
    db.add(PmwbRequirementEvaluation(
        req_id=req_id, sa_name=sa, system_name=system,
        workload=workload, review_workload=review,
    ))
    db.commit()


# ────────────────────────── 阈值与筛选 ──────────────────────────
def test_default_threshold_is_25(db):
    assert rdo.OVERDUE_DAYS_DEFAULT == 25


def test_boundary_25_included_26_excluded(db):
    """严格大于：25 天不入选、26 天入选（老大口径「超过 25 天」）。"""
    add_req(db, "R25")
    add_dev(db, "R25", 25)
    add_req(db, "R26")
    add_dev(db, "R26", 26)

    data = rdo.collect(db, AS_OF)
    ids = [i["req_id"] for i in data["items"]]
    assert ids == ["R26"], ids
    assert data["overdue_count"] == 1
    assert data["total_dev"] == 2


def test_manual_threshold_changes_result(db):
    add_req(db, "R10")
    add_dev(db, "R10", 10)
    add_req(db, "R40")
    add_dev(db, "R40", 40)

    assert rdo.collect(db, AS_OF, 25)["overdue_count"] == 1
    assert rdo.collect(db, AS_OF, 5)["overdue_count"] == 2
    assert rdo.collect(db, AS_OF, 60)["overdue_count"] == 0


def test_not_dev_status_excluded(db):
    add_req(db, "RCLOSED", status="closed")
    add_dev(db, "RCLOSED", 90)
    add_req(db, "RPAUSED", status="paused")
    add_dev(db, "RPAUSED", 90)
    data = rdo.collect(db, AS_OF)
    assert data["overdue_count"] == 0


def test_delivered_date_excludes(db):
    add_req(db, "RDONE", delivered=date(2026, 9, 1))
    add_dev(db, "RDONE", 60)
    data = rdo.collect(db, AS_OF)
    assert data["overdue_count"] == 0
    assert data["already_live"] == 1


def test_ticket_go_live_excludes(db):
    """开发工单已填上线日期 → 视为已上线（与周报/需求分析同源）。"""
    add_req(db, "RTICKET")
    add_dev(db, "RTICKET", 60)
    db.add(PmwbDevTicket(ticket_no="T1", req_id="RTICKET", system_name="CRM",
                         go_live_date=date(2026, 10, 1)))
    db.commit()
    data = rdo.collect(db, AS_OF)
    assert data["overdue_count"] == 0
    assert data["already_live"] == 1


def test_missing_dev_log_reported_not_counted(db):
    add_req(db, "RNODATE")
    data = rdo.collect(db, AS_OF)
    assert data["overdue_count"] == 0
    assert data["no_dev_date"] == ["RNODATE"]


def test_sorted_by_days_desc(db):
    for rid, days in (("RA", 30), ("RB", 70), ("RC", 45)):
        add_req(db, rid)
        add_dev(db, rid, days)
    data = rdo.collect(db, AS_OF)
    assert [i["days"] for i in data["items"]] == [70, 45, 30]


# ────────────────────────── 派生字段 ──────────────────────────
def test_version_overdue_days(db):
    add_req(db, "RV", version_req=date(2026, 9, 24))
    add_dev(db, "RV", 40)
    it = rdo.collect(db, AS_OF)["items"][0]
    assert it["version_required_date"] == "2026-09-24"
    assert it["version_overdue_days"] == 25


def test_risk_levels(db):
    add_req(db, "RP0", priority="P0")
    add_dev(db, "RP0", 27)
    add_req(db, "RP1", priority="P1", version_req=date(2026, 10, 1))
    add_dev(db, "RP1", 30)
    add_req(db, "R61", priority="P2")
    add_dev(db, "R61", 61)
    add_req(db, "R46", priority="P2")
    add_dev(db, "R46", 46)
    add_req(db, "R30", priority="P2")
    add_dev(db, "R30", 30)

    risks = {i["req_id"]: i["risk"] for i in rdo.collect(db, AS_OF)["items"]}
    assert risks["RP0"] == "极高"
    assert risks["RP1"] == "极高"
    assert risks["R61"] == "极高"
    assert risks["R46"] == "高"
    assert risks["R30"] == "中"


def test_workload_review_first_and_sum(db):
    add_req(db, "RW")
    add_dev(db, "RW", 40)
    add_eval(db, "RW", workload=10, review=8)
    add_eval(db, "RW", workload=5, review=None)  # review 空 → 回退 workload
    data = rdo.collect(db, AS_OF)
    assert data["total_workload"] == 13.0
    assert data["items"][0]["workload"] == 13.0


def test_multi_owner_distribution_counts_each(db):
    add_req(db, "RM1", sa="吴雨霜、秦新", system="CRM、电子协议")
    add_dev(db, "RM1", 40)
    add_req(db, "RM2", sa="吴雨霜", system="CRM")
    add_dev(db, "RM2", 30)
    data = rdo.collect(db, AS_OF)
    owners = {x["name"]: x["count"] for x in data["by_owner"]}
    systems = {x["name"]: x["count"] for x in data["by_system"]}
    assert owners == {"吴雨霜": 2, "秦新": 1}
    assert systems == {"CRM": 2, "电子协议": 1}


def test_backfill_flagged(db):
    add_req(db, "RB")
    add_dev(db, "RB", 60, source="backfill")
    it = rdo.collect(db, AS_OF)["items"][0]
    assert it["backfill"] is True
    assert rdo.collect(db, AS_OF)["backfill_count"] == 1


def test_vendor_and_ticket_coverage(db):
    add_req(db, "RVEND")
    add_dev(db, "RVEND", 40)
    db.add(PmwbReqVendorDev(req_id="RVEND", system_name="CRM", dev_status="developing"))
    db.add(PmwbDevTicket(ticket_no="TC-1", req_id="RVEND", system_name="CRM"))
    db.commit()
    data = rdo.collect(db, AS_OF)
    assert data["vendor_tracked_count"] == 1
    assert data["ticket_linked_count"] == 1
    assert data["items"][0]["vendor_dev"][0]["dev_status"] == "developing"


# ────────────────────────── 渲染 ──────────────────────────
def test_render_markdown_structure_and_table(db):
    add_req(db, "R1", name="关于测试需求一", priority="P1", version_req=date(2026, 9, 24))
    add_dev(db, "R1", 53)
    add_eval(db, "R1", workload=12)
    data = rdo.collect(db, AS_OF)
    md = rdo.render_markdown(data, "- **测试**：占位研判")

    assert md.startswith("# 需求开发超期专题分析（统计基准日 2026-10-19）")
    for sec in ("## 一、总体概况", "## 二、超期需求明细", "## 三、分布画像",
                "## 四、研判与建议", "## 五、口径与数据质量说明"):
        assert sec in md, sec
    assert "关于测试需求一" in md
    assert "| 1 | R1 |" in md
    assert "逾期 25 天" in md
    assert "**53**" in md
    assert "占位研判" in md


def test_render_empty_state(db):
    data = rdo.collect(db, AS_OF)
    md = rdo.render_markdown(data, "")
    assert "本期无超过 25 天仍未上线的开发中需求" in md
    assert "本期无超期对象" in md  # 规则兜底研判


def test_render_backfill_marked_in_table(db):
    add_req(db, "RB")
    add_dev(db, "RB", 63, source="backfill")
    md = rdo.render_markdown(rdo.collect(db, AS_OF), "x")
    assert "历史回填" in md


# ────────────────────────── 接口集成 ──────────────────────────
def test_generate_endpoint_creates_dev_overdue_report(db, client, monkeypatch):
    """生成接口：report_type=dev_overdue，走规则兜底也不丢表格数据。"""
    add_req(db, "R1", name="关于接口测试需求", priority="P0")
    add_dev(db, "R1", 27)
    monkeypatch.setattr(wr, "generate_report_markdown", lambda *a, **k: ("", False, None, "no-llm"))

    r = client.post("/api/v1/work-reports/generate", json={
        "report_type": "dev_overdue", "overdue_days": 25,
        "date_end": "2026-10-19",
    })
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["report_type"] == "dev_overdue"
    assert data["report_type_label"] == "需求开发超期专题分析"
    assert data["date_start"] == "2026-10-19" and data["date_end"] == "2026-10-19"
    assert "关于接口测试需求" in data["content"]
    assert "极高" in data["content"]
    assert data["used_llm"] is False


def test_generate_endpoint_honours_manual_threshold(db, client, monkeypatch):
    add_req(db, "R30")
    add_dev(db, "R30", 30)
    monkeypatch.setattr(wr, "generate_report_markdown", lambda *a, **k: ("", False, None, "no-llm"))

    r = client.post("/api/v1/work-reports/generate", json={
        "report_type": "dev_overdue", "overdue_days": 40, "date_end": "2026-10-19",
    })
    assert r.status_code == 200, r.text
    content = r.json()["data"]["content"]
    assert "超过 40 天" in content
    assert "本期无超过 40 天仍未上线的开发中需求" in content


def test_generate_endpoint_uses_llm_insight(db, client, monkeypatch):
    add_req(db, "R1")
    add_dev(db, "R1", 40)
    monkeypatch.setattr(wr, "generate_report_markdown",
                        lambda *a, **k: ("- **AI研判**：建议先动最长滞留项。", True, "kimi", ""))

    r = client.post("/api/v1/work-reports/generate", json={
        "report_type": "dev_overdue", "date_end": "2026-10-19",
    })
    data = r.json()["data"]
    assert data["used_llm"] is True
    assert "AI研判" in data["content"]
    assert data["gen_model"] == "kimi"


def test_clean_insight_strips_fence_and_heading():
    raw = "```markdown\n## 四、研判与建议\n- **要点**：内容\n```"
    assert wr._clean_insight(raw) == "- **要点**：内容"
