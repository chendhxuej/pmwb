"""工作量分析（按月 / 按 SA 汇总人天）单测 —— 2026-10-16。

覆盖口径：
- 归月：dev 环节 entered_at；无记录 / 时间为空 → 排除进 unmonth
- 工作量取值：review_workload 优先，NULL 回退 workload，双空 = missing 计 0
- 一需求多条评估求和；多工单同人合并；跨月归属（全额归 dev 进入月，不摊销）
- sa_name 多人串：split_owners 拆分后**人人计全额**
- 未指派沉底；include_zero 开关；连续月份补零；跨年分桶
- 空库不 500

⚠ 约束锁定：本模块月份分桶必须在 Python 侧做。测试库是内存 SQLite，
用 MySQL 专有 `func.date_format` 会让本文件全红（test_month_bucket_python_side）。

安全：不涉任何邮件发送，不写 MySQL。
"""
from datetime import datetime

from db.models import (
    PmwbRequirementEvaluation,
    PmwbRequirementStageLog,
    SentEmail,
)
from services.workload_analysis import workload_analysis_service

BASE = "/api/v1/workload-analysis/stats"


# ────────────────────────── 造数 helpers ──────────────────────────
def add_req(db, req_id, name="测试需求"):
    """需求宇宙（sent_emails 是唯一来源）。"""
    db.add(SentEmail(req_id=req_id, req_name=name, origin="plugin"))
    db.commit()


def add_dev(db, req_id, when, source="auto"):
    db.add(
        PmwbRequirementStageLog(req_id=req_id, stage="dev", entered_at=when, source=source)
    )
    db.commit()


def add_eval(db, req_id, sa_name=None, workload=None, review=None, system_name=None, req_name=None):
    db.add(
        PmwbRequirementEvaluation(
            req_id=req_id,
            req_name=req_name,
            sa_name=sa_name,
            system_name=system_name,
            workload=workload,
            review_workload=review,
        )
    )
    db.commit()


def stats(client, **params):
    r = client.get(BASE, params=params)
    assert r.status_code == 200, r.text
    return r.json()["data"]


# ────────────────────────── 1. 未归月排除 ──────────────────────────
def test_no_dev_stage_excluded(client, db):
    add_req(db, "R1")
    add_eval(db, "R1", sa_name="张三", workload=10)

    d = stats(client, month_from="2026-01", month_to="2026-12")
    assert d["summary"]["req_count"] == 0
    assert d["requirements"]["items"] == []
    assert len(d["unmonth"]) == 1
    assert d["unmonth"][0]["req_id"] == "R1"
    assert d["unmonth"][0]["reason"] == "no_dev_stage"
    assert d["summary"]["unmonth_req_count"] == 1
    assert any("未纳入月度统计" in w for w in d["warnings"])


def test_dev_time_null_excluded(client, db):
    add_req(db, "R2")
    add_dev(db, "R2", None)
    add_eval(db, "R2", sa_name="张三", workload=10)

    d = stats(client, month_from="2026-01", month_to="2026-12")
    assert d["summary"]["req_count"] == 0
    assert d["unmonth"][0]["reason"] == "dev_time_missing"


# ────────────────────────── 2. 工作量取值口径 ──────────────────────────
def test_review_workload_priority(client, db):
    for rid in ("R1", "R2", "R3"):
        add_req(db, rid)
        add_dev(db, rid, datetime(2026, 8, 5, 10, 0))
    add_eval(db, "R1", sa_name="张三", workload=10, review=5)   # 复核优先 → 5
    add_eval(db, "R2", sa_name="张三", workload=10, review=None)  # 回退初评 → 10
    add_eval(db, "R3", sa_name="张三", workload=None, review=None)  # 双空 → missing 计 0

    d = stats(client, month_from="2026-01", month_to="2026-12")
    got = {r["req_id"]: (r["workload"], r["workload_state"]) for r in d["requirements"]["items"]}
    assert got["R1"] == (5.0, "filled")
    assert got["R2"] == (10.0, "filled")
    assert got["R3"] == (0.0, "missing")
    assert d["summary"]["workload_total"] == 15.0
    assert d["summary"]["missing_workload_req_count"] == 1


# ────────────────────────── 3. SA 归集 ──────────────────────────
def test_multi_sa_full_amount(client, db):
    add_req(db, "R1")
    add_dev(db, "R1", datetime(2026, 8, 5, 10, 0))
    add_eval(db, "R1", sa_name="张三,李四", workload=10)  # 一条挂两人

    d = stats(client, month_from="2026-01", month_to="2026-12")
    by_sa = {x["name"]: x["workload"] for x in d["by_sa"]}
    assert by_sa["张三"] == 10.0
    assert by_sa["李四"] == 10.0
    # 人人计全额 → 合计大于总工作量（预期行为，footnote 已在响应里说明）
    assert d["summary"]["workload_total"] == 10.0
    assert sum(by_sa.values()) == 20.0
    assert "人人计全额" in d["footnote"]


def test_unassigned_sinks(client, db):
    add_req(db, "R1")
    add_req(db, "R2")
    add_dev(db, "R1", datetime(2026, 8, 5, 10, 0))
    add_dev(db, "R2", datetime(2026, 8, 6, 10, 0))
    add_eval(db, "R1", sa_name="张三", workload=10)
    add_eval(db, "R2", sa_name=None, workload=4)  # 无 SA → 未指派

    d = stats(client, month_from="2026-01", month_to="2026-12")
    assert d["by_sa"][-1]["name"] == "未指派"
    assert d["by_sa"][-1]["unassigned"] is True
    assert d["by_sa"][0]["name"] == "张三"
    assert d["summary"]["unassigned_total"] == 4.0
    assert d["summary"]["sa_count"] == 1


# ────────────────────────── 4. 月份区间 ──────────────────────────
def test_month_range_filter(client, db):
    assert client.get(BASE, params={"month_from": "2026-06", "month_to": "2026-01"}).status_code == 400
    assert client.get(BASE, params={"month_from": "202606"}).status_code == 400
    assert client.get(BASE, params={"month_to": "2026-13"}).status_code == 400

    add_req(db, "R1")
    add_dev(db, "R1", datetime(2026, 8, 5, 10, 0))
    add_eval(db, "R1", sa_name="张三", workload=10)
    # 区间外 → 不计入，也不算未归月
    d = stats(client, month_from="2026-01", month_to="2026-06")
    assert d["summary"]["req_count"] == 0
    assert d["unmonth"] == []


def test_cross_year_bucket_and_zero_fill(client, db):
    add_req(db, "A")
    add_req(db, "B")
    add_dev(db, "A", datetime(2025, 12, 20, 9, 0))
    add_dev(db, "B", datetime(2026, 1, 3, 9, 0))
    add_eval(db, "A", sa_name="张三", workload=7)
    add_eval(db, "B", sa_name="张三", workload=3)

    d = stats(client, month_from="2025-12", month_to="2026-02")
    assert d["range"]["months"] == ["2025-12", "2026-01", "2026-02"]
    got = {m["month"]: m["workload"] for m in d["months"]}
    assert got["2025-12"] == 7.0
    assert got["2026-01"] == 3.0
    assert got["2026-02"] == 0.0  # 补零，x 轴不断档
    assert d["summary"]["peak_month"] == "2025-12"


# ────────────────────────── 5. 多评估 / 跨月归属 ──────────────────────────
def test_multi_eval_sum(client, db):
    add_req(db, "R1")
    add_dev(db, "R1", datetime(2026, 8, 5, 10, 0))
    add_eval(db, "R1", sa_name="张三", workload=8, system_name="订单中心")
    add_eval(db, "R1", sa_name="李四", workload=4, system_name="电子协议")

    d = stats(client, month_from="2026-01", month_to="2026-12")
    row = d["requirements"]["items"][0]
    assert row["workload"] == 12.0  # 多条评估求和
    assert row["eval_count"] == 2
    assert row["systems"] == ["电子协议", "订单中心"]


def test_cross_month_full_attribution(client, db):
    """工作量 100% 归入 dev 进入月，不按月摊销。"""
    add_req(db, "R1")
    add_dev(db, "R1", datetime(2026, 3, 31, 23, 0))
    add_eval(db, "R1", sa_name="张三", workload=20)

    d = stats(client, month_from="2026-01", month_to="2026-12")
    assert d["requirements"]["items"][0]["month"] == "2026-03"
    assert d["months"][2]["workload"] == 20.0  # 2026-03
    assert d["months"][3]["workload"] == 0.0   # 2026-04 不摊销


# ────────────────────────── 6. 来源标记 / 开关 / 空态 ──────────────────────────
def test_backfill_source_flag(client, db):
    add_req(db, "R1")
    add_dev(db, "R1", datetime(2026, 8, 5, 10, 0), source="backfill")
    add_eval(db, "R1", sa_name="张三", workload=10)

    d = stats(client, month_from="2026-01", month_to="2026-12")
    assert d["requirements"]["items"][0]["stage_source"] == "backfill"


def test_include_zero_switch(client, db):
    add_req(db, "R1")
    add_req(db, "R2")
    add_dev(db, "R1", datetime(2026, 8, 5, 10, 0))
    add_dev(db, "R2", datetime(2026, 8, 5, 10, 0))
    add_eval(db, "R1", sa_name="张三", workload=10)
    add_eval(db, "R2", sa_name="张三", workload=0, review=0)  # 已评估 0 人天

    d1 = stats(client, month_from="2026-01", month_to="2026-12", include_zero=True)
    assert d1["summary"]["req_count"] == 2
    assert d1["summary"]["zero_workload_req_count"] == 1
    assert d1["by_sa"][0]["workload"] == 10.0

    d2 = stats(client, month_from="2026-01", month_to="2026-12", include_zero=False)
    assert d2["summary"]["req_count"] == 2  # 需求明细不受影响
    assert d2["summary"]["workload_total"] == 10.0


def test_empty_no_500(client, db):
    d = stats(client, month_from="2026-01", month_to="2026-12")
    assert d["summary"]["req_count"] == 0
    assert d["summary"]["workload_total"] == 0
    assert d["by_sa"] == []
    assert d["months"]  # 连续月份补零仍返回
    assert d["unmonth"] == []
    assert d["warnings"] == []


def test_month_bucket_python_side(client, db):
    """锁定实现约束：月份分桶必须 Python 侧做（SQLite 下必须能跑通）。

    若有人改成 MySQL 专有的 func.date_format，本用例会直接抛
    OperationalError: no such function: date_format。
    """
    add_req(db, "R1")
    add_dev(db, "R1", datetime(2026, 8, 5, 10, 0))
    add_eval(db, "R1", sa_name="张三", workload=10)

    d = workload_analysis_service.get_workload_stats(db, month_from="2026-08", month_to="2026-08")
    assert d["range"]["months"] == ["2026-08"]
    assert d["summary"]["workload_total"] == 10.0
    assert d["generated_at"].startswith("20")  # now_cn，禁 utcnow
