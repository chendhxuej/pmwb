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
from utils.master_service import master_service_client as _MC


def _seed_org(name, **kw):
    """播种一个人员中台组织（走被 patch 的 _request → 落到内存实现，不打 DB）。

    ⚠ 播种后必须清缓存：主后端对映射索引有 60s TTL 缓存，否则本用例及后续用例
      会读到播种前的空索引，导致「别名不生效」的假故障。
    """
    out = _MC.create_org({"name": name, **kw})
    _MC.clear_cache()
    return out


def _org_id_by_name(name):
    for o in _MC.list_orgs():
        if o.get("name") == name:
            return o["id"]
    return None

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
    """别名映射 + 系统名不统一兜底（如「电子协议系统」→「电子协议」）。

    映射来源已从本地字典 pmwb_vendor_team 换到**人员中台组织表**：
      · 组织名精确命中   → matched_by = team
      · aliases 精确命中 → matched_by = alias
      · 都落空           → 退回第 4 级唯一包含匹配 contains
    """
    _seed(db)
    _eval(db, "电子协议", 14.0)
    _eval(db, "CRM", 17.0)
    # 中台组织：卓望（target=CRM，别名 卓望团队/zw）
    _seed_org("卓望", org_type="system", target_system_name="CRM", aliases="卓望团队,zw")

    assert sync_from_plugin(db, {"code": REQ, "vendor": "卓望团队"})["matched_by"] == "alias"
    assert sync_from_plugin(db, {"code": REQ, "vendor": "卓望"})["matched_by"] == "team"
    # 清理，避免影响其它用例（fake 是会话级内存态）
    oid = _org_id_by_name("卓望")
    if oid:
        _MC.delete_org(oid, force=True)


# ---------------------------------------------------------------------------
# 二·A2、多对一反向展开（2026-10-19 线上问题）
# ---------------------------------------------------------------------------
def _cleanup_orgs(*names):
    for n in names:
        oid = _org_id_by_name(n)
        if oid:
            _MC.delete_org(oid, force=True)


def test_sync_target_system_reverse_maps_to_active_team(db):
    """标题写合并后的目标系统名（订单中心），评估里记的是原厂家（电子协议）。

    线上实例：REQ_2026第0930620号[订单中心] 关于购物车协议复制步骤简化的需求
      评估 = 电子协议 14 人天 / 订单中心 0 人天 / CRM 17 人天
    旧逻辑：第 1 级精确命中「订单中心」→ 0 人天 → 直接判 zero_workload，
            真正干活的「电子协议」永远同步不到。
    新逻辑：按 target 归组反向展开 → 唯一活跃项 [电子协议] → 直接同步。
    """
    _seed(db)
    _eval(db, "电子协议", 14.0, sa_name="秦新")
    _eval(db, "订单中心", 0.0, sa_name="王辅松")
    _seed_org("电子协议", org_type="system", target_system_name="订单中心")
    _seed_org("政企工作台", org_type="system", target_system_name="订单中心")
    try:
        res = sync_from_plugin(db, {"code": REQ, "vendor": "订单中心"})
        assert res["success"] is True, res
        assert res["system_name"] == "电子协议"
        assert res["matched_by"] == "reverse"
        assert res["is_active"] is True
        # 落地行写的是真正干活的厂家，且带上评估里的 SA
        row = db.query(PmwbReqVendorDev).filter_by(req_id=REQ, system_name="电子协议").first()
        assert row is not None and row.dev_status == "live"
        assert row.sa_name == "秦新"
    finally:
        _cleanup_orgs("电子协议", "政企工作台")


def test_sync_reverse_mapping_ambiguous_returns_candidates(db):
    """同一目标系统下有 2 个活跃团队 → 不猜，返回候选交人工点选。"""
    _seed(db)
    _eval(db, "电子协议", 14.0)
    _eval(db, "政企工作台", 10.0)
    _eval(db, "订单中心", 0.0)
    _seed_org("电子协议", org_type="system", target_system_name="订单中心")
    _seed_org("政企工作台", org_type="system", target_system_name="订单中心")
    try:
        res = sync_from_plugin(db, {"code": REQ, "vendor": "订单中心"})
        assert res["success"] is False
        assert res["reason"] == "vendor_ambiguous"
        # 按工作量降序：电子协议(14) 在 政企工作台(10) 前
        assert res["candidates"] == ["电子协议", "政企工作台"]

        # 用户点选后带 system_name 重试
        ok = sync_from_plugin(db, {"code": REQ, "vendor": "订单中心", "system_name": "政企工作台"})
        assert ok["success"] is True
        assert ok["system_name"] == "政企工作台"
        assert ok["matched_by"] == "explicit"
    finally:
        _cleanup_orgs("电子协议", "政企工作台")


def test_sync_explicit_system_must_be_in_eval(db):
    """手工指定 system_name 也不能乱填，必须在该需求的团队评估里。"""
    _seed(db)
    _eval(db, "CRM", 17.0)
    res = sync_from_plugin(db, {"code": REQ, "vendor": "CRM", "system_name": "BOSS"})
    assert res["success"] is False
    assert res["reason"] == "system_not_in_eval"


def test_reverse_mapping_does_not_cross_target_groups(db):
    """反向展开只在同一 target 组内生效：CRM 不会被 订单中心 那边影响。"""
    _seed(db)
    _eval(db, "电子协议", 14.0)
    _eval(db, "订单中心", 0.0)
    _eval(db, "CRM", 17.0)
    _seed_org("电子协议", org_type="system", target_system_name="订单中心")
    try:
        res = sync_from_plugin(db, {"code": REQ, "vendor": "CRM"})
        assert res["success"] is True
        assert res["system_name"] == "CRM"
        assert res["matched_by"] == "system"
    finally:
        _cleanup_orgs("电子协议")


def test_target_system_options_not_merged_from_history(client: TestClient, db):
    """下拉候选必须与中台保存校验同源，**不得**并入 yxtyg_db 历史名。

    事故（2026-10-19 实测）：8000 把评估表 distinct（电子协议 / DI / 商机平台…）
    并进候选，但中台保存时按自己的候选集校验 → 用户在下拉里选了，保存却报
    「目标系统名不在候选集内」。历史名要能作为目标，得先「新增平台」建成 system 组织。
    """
    _seed(db)
    _eval(db, "_仅历史存在的系统", 5.0)
    body = client.get("/api/v1/meta/target-system-options").json()["data"]
    assert "_仅历史存在的系统" not in body["options"], body
    assert body["options"] == sorted(set(body["options"]))


# ---------------------------------------------------------------------------
# 二·B、降级演练：人员中台不可达
# ---------------------------------------------------------------------------
def test_master_unreachable_skips_team_and_alias_levels(db, monkeypatch):
    """中台不可达 → 跳过 2/3 级（team/alias），只用 1/4 级。

    降级纪律（铁律）：宁可少匹配让人工指定，**绝不**把「拿不到映射」当成
    「空映射」静默放过 —— 那会把本该标黄的工单错误地算成已匹配。
    """
    _seed(db)
    _eval(db, "电子协议", 14.0)
    _eval(db, "CRM", 17.0)
    _seed_org("卓望", org_type="system", target_system_name="CRM", aliases="卓望团队,zw")

    monkeypatch.setattr(_MC, "org_mapping_index", lambda *a, **k: (None, True))
    _MC.clear_cache()

    from services.vendor_dev import _org_mapping, resolve_vendor_system

    assert _org_mapping() == ([], True), "中台不可达时映射必须为空且显式标 degraded"

    # 第 1 级（精确命中评估系统名）不受影响
    assert resolve_vendor_system(db, REQ, "电子协议") == ("电子协议", "system")
    # 第 2/3 级被跳过 → 必须落到 unmatched，绝不能静默命中
    assert resolve_vendor_system(db, REQ, "卓望团队") == (None, "unmatched")
    assert resolve_vendor_system(db, REQ, "卓望") == (None, "unmatched")
    # 第 4 级（唯一包含兜底）仍可用
    assert resolve_vendor_system(db, REQ, "电子协议系统") == ("电子协议", "contains")

    oid = _org_id_by_name("卓望")
    if oid:
        _MC.delete_org(oid, force=True)
    _MC.clear_cache()


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


def test_http_meta_target_system_options(client: TestClient, db):
    """配置下拉的唯一数据源：中台候选 ∪ 评估表历史 distinct ∪ sent_emails distinct。"""
    _seed(db)
    _eval(db, "CRM", 17.0)
    r = client.get("/api/v1/meta/target-system-options")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    data = body["data"]
    assert isinstance(data["options"], list)
    assert "CRM" in data["options"], f"候选集应含评估表历史值，实际 {data['options']}"
    assert isinstance(data["degraded"], bool)
    assert isinstance(data["master_count"], int)


def test_http_vendor_team_dict_endpoints_removed(client: TestClient):
    """旧本地字典端点已下线（映射改由人员中台维护）。"""
    assert client.get("/api/v1/meta/vendor-teams").status_code == 404
    assert client.get("/api/v1/plugins/vendor-teams").status_code == 404


def test_http_plugin_workorder_sync(client: TestClient, db):
    _seed(db)
    _eval(db, "CRM", 17.0)
    r = client.post("/api/v1/plugins/workorder-sync", json={"code": REQ, "vendor": "CRM"})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True and body["dev_status"] == "live"
    # 扁平协议：插件直连，不套 code/data
    assert "code" not in body


def test_http_meta_org_mapping_index(client: TestClient, db):
    """只读映射总览（需求页弹窗用）：返回中台 system 类组织的三元组。"""
    _seed_org("索引组织", org_type="system", target_system_name="CRM", aliases="idx,索")
    r = client.get("/api/v1/meta/org-mapping-index")
    assert r.status_code == 200
    rows = r.json()["data"]
    assert isinstance(rows, list)
    hit = [x for x in rows if x.get("org_name") == "索引组织"]
    assert hit, f"新播种组织未出现在映射索引，实际 {[x.get('org_name') for x in rows]}"
    assert hit[0]["target_system_name"] == "CRM"
    assert hit[0]["aliases"] == "idx,索"
    assert hit[0]["org_type"] == "system"
    oid = _org_id_by_name("索引组织")
    if oid:
        _MC.delete_org(oid, force=True)
    _MC.clear_cache()


def test_http_plugin_sync_survives_master_outage(client: TestClient, db, monkeypatch):
    """中台挂掉时插件同步不得 500（插件侧零改动的前提），且不得伪造成已匹配。"""
    _seed(db)
    _eval(db, "CRM", 17.0)
    monkeypatch.setattr(_MC, "org_mapping_index", lambda *a, **k: (None, True))
    _MC.clear_cache()

    r = client.post("/api/v1/plugins/workorder-sync", json={"code": REQ, "vendor": "CRM"})
    assert r.status_code == 200, r.text
    body = r.json()
    # 第 1 级仍命中，链路没被打断
    assert body["success"] is True and body["matched_by"] == "system"

    r2 = client.post("/api/v1/plugins/workorder-sync", json={"code": REQ, "vendor": "某个未知团队"})
    assert r2.status_code == 200, r2.text
    body2 = r2.json()
    assert body2["success"] is False
    assert body2["reason"] == "vendor_not_matched"
    assert "matched_by" not in body2 or body2.get("matched_by") != "team"


def test_http_status_domains_contains_vendor_dev(client: TestClient, db):
    r = client.get("/api/v1/meta/status-domains")
    doms = r.json()["data"]["domains"]
    assert "vendor_dev" in doms
    labels = {s["value"]: s["label"] for s in doms["vendor_dev"]["statuses"]}
    assert labels == {
        "pending": "待开发", "developing": "开发中",
        "live": "已上线", "completed": "已完成",
    }
