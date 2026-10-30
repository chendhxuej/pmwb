"""热点投诉模块测试（方案 v3.0 第②模块）。

覆盖：TOP 排序 / 环比四态标注（new/up/flat/down）/ 闭环反弹检测 /
在办问题关联 / 代表工单 / 端点。
"""

from datetime import datetime, timedelta

import pytest

from db.models import PmwbComplaintCategory, PmwbComplaintProblem, PmwbComplaintTicket
from services.complaint import hotspots


def _add(db, obj):
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def _seed_week(db, week, l2, cnt, start_date):
    """在某周内造 cnt 条工单（以 start_date 为周一，逐日分散）。"""
    for i in range(cnt):
        _add(db, PmwbComplaintTicket(
            ticket_no=f"{week}-{l2}-{i}", week=week,
            created_time=start_date + timedelta(days=i % 5, hours=i),
            city="苏州", content=f"内容 {l2} {i}", status="已回复",
            category_l1="系统问题", category_l2=l2, classify_by="ai", dispatch_count=1,
        ))


def test_weekly_hotspots_ranking_and_flags(db):
    # W44：场景A 5 单（上周 2 → up）、场景B 3 单（上周 0 → new）、场景C 2 单（上周 5 → down）
    _seed_week(db, "2026-W44", "多出账与费用突增", 5, datetime(2026, 10, 26))
    _seed_week(db, "2026-W44", "施工单未触发", 3, datetime(2026, 10, 27))
    _seed_week(db, "2026-W44", "退费与账单争议", 2, datetime(2026, 10, 28))
    _seed_week(db, "2026-W43", "多出账与费用突增", 2, datetime(2026, 10, 19))
    _seed_week(db, "2026-W43", "退费与账单争议", 5, datetime(2026, 10, 19))

    res = hotspots.weekly_hotspots(db, week="2026-W44", top_n=10)
    assert res["week"] == "2026-W44" and res["prev_week"] == "2026-W43"
    assert res["total"] == 10
    items = {it["l2"]: it for it in res["items"]}
    a, b, c = items["多出账与费用突增"], items["施工单未触发"], items["退费与账单争议"]
    # 排序：按本周量倒序
    assert res["items"][0]["l2"] == "多出账与费用突增"
    assert (a["cur"], a["prev"], a["flag"]) == (5, 2, "up")
    assert (b["cur"], b["flag"]) == (3, "new")
    assert (c["cur"], c["flag"]) == (2, "down")
    # 代表工单 ≤2 条
    assert 0 < len(a["sample_tickets"]) <= 2


def test_hotspots_rebound_and_open_problems(db):
    _seed_week(db, "2026-W44", "订单状态滞留未流转", 4, datetime(2026, 10, 26))
    _seed_week(db, "2026-W43", "订单状态滞留未流转", 4, datetime(2026, 10, 19))
    _add(db, PmwbComplaintProblem(
        problem_no="CPB-2026W40-01", source_type="scan", title="订单滞留",
        category_l1="流程优化", category_l2="订单状态滞留未流转", status="closed",
        rule_hits="top_scene", evidence="[]", first_week="2026-W40", last_week="2026-W42",
        week_cnt=0, peak_cnt=8, total_cnt=20, active_weeks=0, quiet_weeks=2, reopen_flag=0,
    ))
    _add(db, PmwbComplaintProblem(
        problem_no="CPB-2026W44-09", source_type="manual", title="电视账号同步",
        category_l1="数据问题", category_l2="电视与机顶盒账号未同步", status="open",
        rule_hits="", evidence="[]", first_week="2026-W44", last_week="2026-W44",
        week_cnt=3, peak_cnt=3, total_cnt=3, active_weeks=1, quiet_weeks=0, reopen_flag=0,
    ))
    _seed_week(db, "2026-W44", "电视与机顶盒账号未同步", 3, datetime(2026, 10, 26))

    res = hotspots.weekly_hotspots(db, week="2026-W44")
    items = {it["l2"]: it for it in res["items"]}
    order = items["订单状态滞留未流转"]
    assert order["rebound"] is True  # 已闭环 + 本周量未降 → 反弹
    assert order["closed_problem_no"] == "CPB-2026W40-01"
    tv = items["电视与机顶盒账号未同步"]
    assert tv["open_problems"][0]["problem_no"] == "CPB-2026W44-09"
    assert tv["rebound"] is False


def test_hotspots_empty_db(db):
    res = hotspots.weekly_hotspots(db)
    assert res["week"] == "" and res["items"] == []


def test_api_hotspots(client, db):
    _seed_week(db, "2026-W44", "多出账与费用突增", 3, datetime(2026, 10, 26))
    r = client.get("/api/v1/complaint/hotspots")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    assert body["data"]["week"] == "2026-W44"
    assert body["data"]["items"][0]["l2"] == "多出账与费用突增"
