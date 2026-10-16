"""需求「厂家开发状态」回归（2026-10-16 新增）。

覆盖老大确认的三条核心口径：
  1. 厂家清单 = 团队评估中 **workload > 0** 的系统（0 与 NULL 一并剔除）
  2. 插件同步 **幂等、只前进不回退**（completed 不被覆盖回 live）
  3. 完成联动：**活跃厂家全 completed** 才触发（0 人天厂家不参与判定），
     实际上线日 = 当周周四且 **仅当为空时写入**
"""
from datetime import date

from fastapi.testclient import TestClient

from db.models import (
    PmwbReqManual,
    PmwbReqVendorDev,
    PmwbRequirementEvaluation,
    PmwbRequirementExt,
    PmwbVendorTeam,
    SentEmail,
    now_cn,
)
from services.vendor_dev import (
    active_team_systems,
    list_vendor_devs,
    sync_from_plugin,
    update_vendor_dev,
    week_thursday,
)

REQ = "REQ-VD-001"


def _seed(db, req_id=REQ):
    """建一条需求源行 + 一条 ext（dev 状态、实际上线日为空）。"""
    mail = SentEmail(
        req_id=req_id, req_name="购物车协议复制步骤简化的需求",
        proposer="张三", propose_time="2026-09-01", system_name="CRM",
        sa_name="李四", send_datetime="2026-09-01", is_involved=1,
        dev_ticket_no="TICKET-VD-001", involve_dev="是",
    )
    db.add(mail)
    db.add(PmwbRequirementExt(req_id=req_id, status="dev", delivered_date=None))
    db.commit()
    return mail


def _eval(db, system_name, workload, sa_name="王五", req_id=REQ):
    ev = PmwbRequirementEvaluation(
        req_id=req_id, system_name=system_name, sa_name=sa_name, workload=workload
    )
    db.add(ev)
    db.commit()
    return ev


# ---------------------------------------------------------------------------
# 一、厂家清单唯一源
# ---------------------------------------------------------------------------
def test_active_team_systems_excludes_zero_and_null(db):
    _seed(db)
    _eval(db, "CRM", 17.0)
    _eval(db, "电子协议", 14.0)
    _eval(db, "订单中心", 0)          # 0 人天 → 剔除
    _eval(db, "生产运营平台", None)     # NULL → 剔除

    names = [a["system_name"] for a in active_team_systems(db, REQ)]
    assert names == ["CRM", "电子协议"], f"0 与 NULL 人天必须被剔除，实际 {names}"


def test_list_vendor_devs_auto_creates_active_rows(db):
    _seed(db)
    _eval(db, "CRM", 17.0)
    _eval(db, "电子协议", 14.0)
    _eval(db, "订单中心", 0)

    data = list_vendor_devs(db, REQ)
    assert data["auto_created"] == 2
    assert data["active_count"] == 2
    assert [i["system_name"] for i in data["items"]] == ["CRM", "电子协议"]
    assert all(i["dev_status"] == "developing" for i in data["items"])


def test_inactive_row_is_kept_and_flagged(db):
    """0 人天厂家行（force 同步产生的）保留但 is_active=False，永不自动删。"""
    _seed(db)
    _eval(db, "CRM", 17.0)
    _eval(db, "订单中心", 0)
    sync_from_plugin(db, {"code": REQ, "vendor": "订单中心", "force": True})

    data = list_vendor_devs(db, REQ)
    row = next(i for i in data["items"] if i["system_name"] == "订单中心")
    assert row["is_active"] is False
    assert row["workload"] == 0


# ---------------------------------------------------------------------------
# 二、插件同步
# ---------------------------------------------------------------------------
def test_sync_from_plugin_sets_live(db):
    _seed(db)
    _eval(db, "CRM", 17.0)
    res = sync_from_plugin(db, {"code": REQ, "vendor": "CRM"})
    assert res["success"] is True
    assert res["dev_status"] == "live"
    assert res["dev_status_label"] == "已上线"
    assert res["matched_by"] == "system"


def test_sync_is_idempotent_and_never_regresses(db):
    """只前进不回退：已 completed 的厂家不被插件覆盖回 live。"""
    _seed(db)
    _eval(db, "CRM", 17.0)
    sync_from_plugin(db, {"code": REQ, "vendor": "CRM"})

    row = db.query(PmwbReqVendorDev).filter(
        PmwbReqVendorDev.req_id == REQ, PmwbReqVendorDev.system_name == "CRM"
    ).first()
    update_vendor_dev(db, row.id, {"dev_status": "completed"})

    res = sync_from_plugin(db, {"code": REQ, "vendor": "CRM"})
    assert res["success"] is True
    assert res["dev_status"] == "completed", "已完成状态不得被插件同步回退"


def test_sync_zero_workload_rejected_unless_forced(db):
    _seed(db)
    _eval(db, "CRM", 17.0)
    _eval(db, "订单中心", 0)

    res = sync_from_plugin(db, {"code": REQ, "vendor": "订单中心"})
    assert res["success"] is False
    assert res["reason"] == "zero_workload"

    res = sync_from_plugin(db, {"code": REQ, "vendor": "订单中心", "force": True})
    assert res["success"] is True
    assert res["is_active"] is False
    assert res["forced"] is True


def test_sync_unknown_vendor_not_matched(db):
    _seed(db)
    _eval(db, "CRM", 17.0)
    res = sync_from_plugin(db, {"code": REQ, "vendor": "不存在的厂家"})
    assert res["success"] is False
    assert res["reason"] == "vendor_not_matched"


def test_resolve_vendor_system_alias_and_fuzzy(db):
    """别名映射 + 系统名不统一兜底（如「电子协议系统」→「电子协议」）。"""
    _seed(db)
    _eval(db, "电子协议", 14.0)
    _eval(db, "CRM", 17.0)
    db.add(PmwbVendorTeam(team_name="卓望", system_name="CRM", aliases="卓望团队,zw"))
    db.commit()

    assert sync_from_plugin(db, {"code": REQ, "vendor": "卓望团队"})["matched_by"] == "alias"
    assert sync_from_plugin(db, {"code": REQ, "vendor": "卓望"})["matched_by"] == "team"
    # 系统名不统一：唯一包含匹配
    assert sync_from_plugin(db, {"code": REQ, "vendor": "电子协议系统"})["matched_by"] == "contains"


# ---------------------------------------------------------------------------
# 三、完成联动
# ---------------------------------------------------------------------------
def _all_completed(db):
    for row in db.query(PmwbReqVendorDev).filter(PmwbReqVendorDev.req_id == REQ).all():
        update_vendor_dev(db, row.id, {"dev_status": "completed"})


def test_finalize_sets_closed_and_week_thursday(db):
    _seed(db)
    _eval(db, "CRM", 17.0)
    _eval(db, "电子协议", 14.0)
    list_vendor_devs(db, REQ)          # 自动补行

    res = update_vendor_dev(db, _row_id(db, "CRM"), {"dev_status": "completed"})
    assert res["finalized"] is None, "还有厂家未完成时不得联动"

    res = update_vendor_dev(db, _row_id(db, "电子协议"), {"dev_status": "completed"})
    assert res["finalized"]["finalized"] is True

    ext = db.query(PmwbRequirementExt).filter(PmwbRequirementExt.req_id == REQ).first()
    assert ext.status == "closed"
    assert ext.delivered_date == week_thursday(now_cn().date())


def _row_id(db, system_name):
    row = db.query(PmwbReqVendorDev).filter(
        PmwbReqVendorDev.req_id == REQ, PmwbReqVendorDev.system_name == system_name
    ).first()
    return row.id


def test_finalize_does_not_overwrite_existing_delivered_date(db):
    """实际上线日**仅当为空时写入**，保护老大手填的数据。"""
    _seed(db)
    ext = db.query(PmwbRequirementExt).filter(PmwbRequirementExt.req_id == REQ).first()
    ext.delivered_date = date(2026, 9, 1)
    db.commit()

    _eval(db, "CRM", 17.0)
    list_vendor_devs(db, REQ)
    update_vendor_dev(db, _row_id(db, "CRM"), {"dev_status": "completed"})

    db.refresh(ext)
    assert ext.delivered_date == date(2026, 9, 1), "已填的实际上线日不得被覆盖"


def test_finalize_idempotent_when_already_closed(db):
    _seed(db)
    _eval(db, "CRM", 17.0)
    list_vendor_devs(db, REQ)
    update_vendor_dev(db, _row_id(db, "CRM"), {"dev_status": "completed"})

    row = db.query(PmwbReqVendorDev).filter(
        PmwbReqVendorDev.req_id == REQ, PmwbReqVendorDev.system_name == "CRM"
    ).first()
    res = update_vendor_dev(db, row.id, {"dev_status": "completed"})
    assert res["finalized"]["skipped"] is True


def test_zero_workload_vendor_does_not_block_finalize(db):
    """0 人天厂家不参与联动判定——否则永远凑不齐『全部已完成』。"""
    _seed(db)
    _eval(db, "CRM", 17.0)
    _eval(db, "订单中心", 0)
    list_vendor_devs(db, REQ)          # 先补建活跃厂家行
    sync_from_plugin(db, {"code": REQ, "vendor": "订单中心", "force": True})

    res = update_vendor_dev(db, _row_id(db, "CRM"), {"dev_status": "completed"})
    assert res["finalized"]["finalized"] is True, "0 人天厂家不得阻塞上线联动"


def test_no_active_vendor_means_no_finalize(db):
    _seed(db)
    _eval(db, "订单中心", 0)
    sync_from_plugin(db, {"code": REQ, "vendor": "订单中心", "force": True})
    res = update_vendor_dev(db, _row_id(db, "订单中心"), {"dev_status": "completed"})
    assert res["finalized"] is None


def test_invalid_transition_rejected(db):
    _seed(db)
    _eval(db, "CRM", 17.0)
    list_vendor_devs(db, REQ)
    update_vendor_dev(db, _row_id(db, "CRM"), {"dev_status": "completed"})
    try:
        update_vendor_dev(db, _row_id(db, "CRM"), {"dev_status": "pending"})
        assert False, "已完成 → 待开发 应被拒绝"
    except ValueError:
        pass


def test_week_thursday_monday_based():
    """周一为一周起点：周日仍归属「本周」（周一算起），故其周四即本周四。"""
    assert week_thursday(date(2026, 10, 12)) == date(2026, 10, 15)   # 周一
    assert week_thursday(date(2026, 10, 15)) == date(2026, 10, 15)   # 周四当天
    assert week_thursday(date(2026, 10, 16)) == date(2026, 10, 15)   # 周五 → 仍本周四
    assert week_thursday(date(2026, 10, 18)) == date(2026, 10, 15)   # 周日 → 仍本周四
    assert week_thursday(date(2026, 10, 19)) == date(2026, 10, 22)   # 下周一 → 下周四


# ---------------------------------------------------------------------------
# 四、操作手册卡片共用同一份团队清单
# ---------------------------------------------------------------------------
def test_manual_systems_shares_vendor_team_list(db):
    from services.requirement_stage import list_manual_systems

    _seed(db)
    _eval(db, "CRM", 17.0)
    _eval(db, "订单中心", 0)
    data = list_manual_systems(db, REQ)
    names = [s["system_name"] for s in data["systems"]]
    assert "订单中心" not in names, "手册卡片须与厂家清单同口径剔除 0 人天"


def test_manual_systems_keeps_uploaded_manual_asset(db):
    """已上传手册的系统即便被 0 人天剔除，仍须展示（资产保护）。"""
    from services.requirement_stage import list_manual_systems

    _seed(db)
    _eval(db, "CRM", 17.0)
    _eval(db, "订单中心", 0)
    db.add(PmwbReqManual(
        req_id=REQ, system_name="订单中心", file_name="操作手册.docx", local_path="/tmp/x.docx"
    ))
    db.commit()

    data = list_manual_systems(db, REQ)
    row = next(s for s in data["systems"] if s["system_name"] == "订单中心")
    assert row["is_zero_workload"] is True
    assert row["manual"] is not None


# ---------------------------------------------------------------------------
# 五、HTTP 契约
# ---------------------------------------------------------------------------
def test_http_vendor_dev_endpoints(client: TestClient, db):
    _seed(db)
    _eval(db, "CRM", 17.0)
    q = f"/api/v1/requirements/{REQ}/vendor-devs"

    r = client.get(q)
    assert r.status_code == 200
    assert r.json()["data"]["active_count"] == 1

    row_id = r.json()["data"]["items"][0]["id"]
    r = client.put(f"{q}/{row_id}", json={"dev_status": "completed"})
    assert r.status_code == 200
    assert "已上线" in r.json().get("message", "")

    r = client.put(f"{q}/{row_id}", json={"dev_status": "pending"})
    assert r.status_code == 400

    r = client.delete(f"{q}/{row_id}")
    assert r.json()["data"]["deleted"] is True
    r = client.delete(f"{q}/{row_id}")
    assert r.json()["data"]["deleted"] is False   # 既有删除契约：不存在返 False


def test_http_meta_vendor_teams(client: TestClient, db):
    r = client.post("/api/v1/meta/vendor-teams",
                    json={"team_name": "卓望", "system_name": "CRM", "aliases": "zw"})
    assert r.status_code == 200
    tid = r.json()["data"]["id"]

    r = client.post("/api/v1/meta/vendor-teams", json={"team_name": "卓望", "system_name": "CRM"})
    assert r.status_code == 400, "team_name 唯一，重复应拒绝"

    assert client.get("/api/v1/meta/vendor-teams").status_code == 200
    assert client.put(f"/api/v1/meta/vendor-teams/{tid}", json={"aliases": "zw,卓望团队"}).status_code == 200
    assert client.delete(f"/api/v1/meta/vendor-teams/{tid}").json()["data"]["deleted"] is True


def test_http_plugin_workorder_sync(client: TestClient, db):
    _seed(db)
    _eval(db, "CRM", 17.0)
    r = client.post("/api/v1/plugins/workorder-sync", json={"code": REQ, "vendor": "CRM"})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True and body["dev_status"] == "live"
    # 扁平协议：插件直连，不套 code/data
    assert "code" not in body


def test_http_status_domains_contains_vendor_dev(client: TestClient, db):
    r = client.get("/api/v1/meta/status-domains")
    doms = r.json()["data"]["domains"]
    assert "vendor_dev" in doms
    labels = {s["value"]: s["label"] for s in doms["vendor_dev"]["statuses"]}
    assert labels == {
        "pending": "待开发", "developing": "开发中",
        "live": "已上线", "completed": "已完成",
    }
