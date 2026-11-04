"""问题族（业务链路）聚合测试。

覆盖 2026-11-04 引入的「族」口径：簇是个案粒度，报表按链路族看趋势。
重点守三条：
  1. 环节 → 族是**确定性映射**（新增环节漏配会落 other，不允许静默丢数据）；
  2. 环比一律**日均对比**——历史坑：周三看当周，用 7 天摊薄会算出 -70% 假暴跌；
  3. 一次性个案（簇仅 1 单）单独计数，不混进族的问题列表。
"""

from datetime import datetime, timedelta

from constants import complaint_theme as T
from db.models import PmwbComplaintRootcause, PmwbComplaintTicket
from services.complaint import themes as TH


def _add(db, obj):
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def _cluster(db, no, stage, cnt, first_week="2026-W40", is_defect=1):
    return _add(db, PmwbComplaintRootcause(
        rootcause_no=no, title=f"{no} 测试簇", status="open", ticket_cnt=cnt,
        fault_stage=stage, fault_system="订单中心", first_week=first_week,
        is_defect=is_defect,
    ))


def _ticket(db, no, rc, week, month, day):
    return _add(db, PmwbComplaintTicket(
        ticket_no=no, week=week,
        created_time=datetime(2026, month, day, 10, 0),
        city="苏州", content="x", status="已回复", dispatch_count=1,
        rootcause_no=rc, known_flag=0,
    ))


def test_stage_to_theme_mapping():
    """环节映射确定性：已知环节落对族，未知环节落 other 不丢。"""
    assert T.theme_of("订单开通") == "order_fulfill"
    assert T.theme_of("装维交付") == "order_fulfill"      # 同属交付链路，必须归一
    assert T.theme_of("业务激活") == "activation"
    assert T.theme_of("使用咨询") == "consult"
    assert T.theme_of("从没见过的环节") == "other"
    assert T.theme_of("") == "other"
    # 每个映射目标都必须是已定义的族，防止手滑写错 key
    for v in T.STAGE_TO_THEME.values():
        assert v in T.THEME_KEYS


def test_theme_stats_daily_avg_wow(db):
    """环比按日均：本周 3 单/1 天 vs 上周 7 单/7 天 → 日均 3.0 vs 1.0 = +200%。"""
    _cluster(db, "RC-T1", "订单开通", cnt=3)
    _cluster(db, "RC-T2", "订单开通", cnt=7, first_week="2026-W39")
    # 本周（W40 = 9/28~10/4）3 单集中同一天
    for i in range(3):
        _ticket(db, f"W40-{i}", "RC-T1", "2026-W40", month=9, day=29)
    # 上周（W39 = 9/21~9/27）7 单铺满 7 天
    for i in range(7):
        _ticket(db, f"W39-{i}", "RC-T2", "2026-W39", month=9, day=21 + i)

    r = TH.theme_stats(db, week="2026-W40")
    assert r["wow_basis"] == "daily_avg"
    assert r["week_days"] == 1 and r["prev_days"] == 7

    fam = {t["key"]: t for t in r["themes"]}["order_fulfill"]
    assert fam["week_cnt"] == 3 and fam["prev_cnt"] == 7
    assert fam["avg"] == 3.0 and fam["prev_avg"] == 1.0
    assert fam["wow"] == 200.0


def test_theme_stats_marks_low_sample(db):
    """样本过小必须有标记，避免 1 单 vs 2 单被当成趋势。"""
    _cluster(db, "RC-T3", "计费出账", cnt=1)
    _ticket(db, "B-1", "RC-T3", "2026-W40", month=9, day=29)
    r = TH.theme_stats(db, week="2026-W40")
    fam = {t["key"]: t for t in r["themes"]}["billing"]
    assert fam["low_sample"] is True
    assert fam["wow"] is None  # 上周 0 单，不给假增幅


def test_cases_counted_separately(db):
    """一次性个案（簇仅 1 单）单独计数，不出现在族的 top_clusters 里。"""
    _cluster(db, "RC-T4", "订单开通", cnt=1)
    _cluster(db, "RC-T5", "订单开通", cnt=6)
    _ticket(db, "C-1", "RC-T4", "2026-W40", month=9, day=29)
    for i in range(6):
        _ticket(db, f"C-big-{i}", "RC-T5", "2026-W40", month=9, day=29)

    r = TH.theme_stats(db, week="2026-W40")
    assert r["cases"]["cluster_cnt"] == 1
    assert r["cases"]["ticket_cnt"] == 1
    fam = {t["key"]: t for t in r["themes"]}["order_fulfill"]
    assert [c["rc_no"] for c in fam["top_clusters"]] == ["RC-T5"]
    # 族单量仍包含个案单量（个案只是不单独列示，不能从统计里消失）
    assert fam["week_cnt"] == 7


def test_non_defect_theme_present(db):
    """咨询类簇仍出现在族里（用于说明「多少单其实是问询」），只是不进台账。"""
    _cluster(db, "RC-T6", "使用咨询", cnt=4, is_defect=0)
    for i in range(4):
        _ticket(db, f"Q-{i}", "RC-T6", "2026-W40", month=9, day=29)
    r = TH.theme_stats(db, week="2026-W40")
    fam = {t["key"]: t for t in r["themes"]}
    assert "consult" in fam and fam["consult"]["week_cnt"] == 4
