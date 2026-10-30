"""主动优化工单「关联需求文号」一对多 —— 单测（2026-10-16）。

背景：主动优化原只能挂一个需求文号（pmwb_active_optimization.req_id 单列），
改为一对多关联表 pmwb_active_optimization_req 后，需覆盖：
- 新增/全量覆盖/增量/删除/级联删除
- 防重复（uk_opt_req + 应用层差集）
- 无效文号（需求宇宙 = SELECT DISTINCT req_id FROM sent_emails）
- 空值 / 超长 / 数量上限
- 存量 req_id 幂等迁移
- 历史列回填（邮件模板兼容）

安全：本用例不涉任何邮件发送；测试库为内存 SQLite（conftest）。
"""
from db.models import PmwbActiveOptimization, PmwbActiveOptimizationReq, SentEmail
from services.active_optimization import active_optimization_service

BASE = "/api/v1/active-optimizations"


# ────────────────────────── 造数 helpers ──────────────────────────
def make_req(db, req_id: str, name: str = "测试需求"):
    """造一条需求宇宙记录（sent_emails 是需求宇宙的唯一来源）。"""
    obj = SentEmail(req_id=req_id, req_name=name, origin="plugin")
    db.add(obj)
    db.commit()
    return obj


def make_opt(db, title: str = "测试优化工单", req_id: str = None):
    obj = PmwbActiveOptimization(title=title, req_id=req_id, status="pending", priority="P2")
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def links_of(db, opt_id: int):
    return (
        db.query(PmwbActiveOptimizationReq)
        .filter(PmwbActiveOptimizationReq.opt_id == opt_id)
        .order_by(PmwbActiveOptimizationReq.id.asc())
        .all()
    )


# ────────────────────────── 1. 基础写入 ──────────────────────────
def test_add_links_ok(client, db):
    make_req(db, "R001", "需求一")
    make_req(db, "R002", "需求二")
    opt = make_opt(db)

    r = client.put(f"{BASE}/{opt.id}/req-links", json={"req_ids": ["R001", "R002"]})
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["req_ids"] == ["R001", "R002"]
    assert d["created"] == ["R001", "R002"]

    rows = links_of(db, opt.id)
    assert len(rows) == 2
    # req_name 冗余快照
    assert rows[0].req_name == "需求一"

    # 列表接口返回 req_ids 数组
    lst = client.get(BASE).json()["data"]["items"]
    assert lst[0]["req_ids"] == ["R001", "R002"]
    assert len(lst[0]["req_links"]) == 2


def test_duplicate_rejected(client, db):
    make_req(db, "R001")
    opt = make_opt(db)

    r1 = client.put(f"{BASE}/{opt.id}/req-links", json={"req_ids": ["R001", "R001"]})
    assert r1.json()["data"]["req_ids"] == ["R001"]  # 入参内去重
    assert len(links_of(db, opt.id)) == 1

    r2 = client.put(f"{BASE}/{opt.id}/req-links", json={"req_ids": ["R001"]})
    assert r2.json()["data"]["skipped_duplicate"] == ["R001"]
    assert len(links_of(db, opt.id)) == 1  # 仍只有 1 行，未被重复插入


# ────────────────────────── 2. 无效文号校验 ──────────────────────────
def test_invalid_req_id(client, db):
    make_req(db, "R001")
    opt = make_opt(db)

    # 默认 strict=false：部分成功，无效文号进 rejected_invalid
    r = client.put(f"{BASE}/{opt.id}/req-links", json={"req_ids": ["R001", "GHOST"]})
    d = r.json()["data"]
    assert d["req_ids"] == ["R001"]
    assert d["rejected_invalid"] == ["GHOST"]

    # strict=true：整体拒绝
    r2 = client.put(f"{BASE}/{opt.id}/req-links", json={"req_ids": ["GHOST"], "strict": True})
    assert r2.status_code == 400, r2.text
    assert len(links_of(db, opt.id)) == 1  # 未产生副作用


def test_blank_and_overflow(client, db):
    make_req(db, "R001")
    opt = make_opt(db)

    # 空白项被丢弃 → 等价于清空
    r = client.put(f"{BASE}/{opt.id}/req-links", json={"req_ids": ["  ", ""]})
    assert r.status_code == 200
    assert r.json()["data"]["req_ids"] == []

    # 超长 400
    r2 = client.put(f"{BASE}/{opt.id}/req-links", json={"req_ids": ["X" * 256]})
    assert r2.status_code == 400

    # 数量上限 400
    r3 = client.put(f"{BASE}/{opt.id}/req-links", json={"req_ids": [f"R{i}" for i in range(51)]})
    assert r3.status_code == 400


def test_opt_not_found(client, db):
    r = client.put(f"{BASE}/9999/req-links", json={"req_ids": ["R001"]})
    assert r.status_code == 404


# ────────────────────────── 3. 全量覆盖 / 删除 ──────────────────────────
def test_full_replace_removes_old(client, db):
    for rid in ("A", "B", "C"):
        make_req(db, rid)
    opt = make_opt(db)

    client.put(f"{BASE}/{opt.id}/req-links", json={"req_ids": ["A", "B"]})
    assert [x.req_id for x in links_of(db, opt.id)] == ["A", "B"]

    r = client.put(f"{BASE}/{opt.id}/req-links", json={"req_ids": ["A", "C"]})
    d = r.json()["data"]
    assert d["removed"] == ["B"]
    assert d["created"] == ["C"]
    assert d["req_ids"] == ["A", "C"]

    # 全空 = 清空关联
    r2 = client.put(f"{BASE}/{opt.id}/req-links", json={"req_ids": []})
    assert r2.json()["data"]["req_ids"] == []
    assert links_of(db, opt.id) == []


def test_incremental_add_keeps_existing(client, db):
    for rid in ("A", "B"):
        make_req(db, rid)
    opt = make_opt(db)

    client.put(f"{BASE}/{opt.id}/req-links", json={"req_ids": ["A"]})
    r = client.post(f"{BASE}/{opt.id}/req-links", json={"req_ids": ["B"]})
    assert r.json()["data"]["req_ids"] == ["A", "B"]

    # 增量传空 → 400
    r2 = client.post(f"{BASE}/{opt.id}/req-links", json={"req_ids": []})
    assert r2.status_code == 400


def test_delete_link(client, db):
    make_req(db, "A")
    opt = make_opt(db)
    client.put(f"{BASE}/{opt.id}/req-links", json={"req_ids": ["A"]})
    link_id = links_of(db, opt.id)[0].id

    r = client.delete(f"{BASE}/{opt.id}/req-links/{link_id}")
    assert r.json()["data"]["deleted"] is True
    # 重复删：deleted=False（沿用项目既有删除契约，不报 404）
    r2 = client.delete(f"{BASE}/{opt.id}/req-links/{link_id}")
    assert r2.json()["data"]["deleted"] is False

    # 按文号批量删
    client.put(f"{BASE}/{opt.id}/req-links", json={"req_ids": ["A"]})
    r3 = client.delete(f"{BASE}/{opt.id}/req-links", params={"req_id": "A"})
    assert r3.json()["data"]["deleted"] == 1


def test_delete_opt_cascades(client, db):
    make_req(db, "A")
    opt = make_opt(db)
    client.put(f"{BASE}/{opt.id}/req-links", json={"req_ids": ["A"]})
    assert len(links_of(db, opt.id)) == 1

    assert client.delete(f"{BASE}/{opt.id}").json()["data"] is True
    assert links_of(db, opt.id) == []  # 关联行一并清理


# ────────────────────────── 4. 检索命中关联表 ──────────────────────────
def test_keyword_hits_link_table(client, db):
    """只写关联表（主表 req_id 为空）时，keyword 仍要能搜到。"""
    make_req(db, "ZZTOP")
    opt = make_opt(db, title="无关标题", req_id=None)
    client.put(f"{BASE}/{opt.id}/req-links", json={"req_ids": ["ZZTOP"]})

    r = client.get(BASE, params={"keyword": "ZZTOP"}).json()["data"]
    assert r["total"] == 1
    assert r["items"][0]["id"] == opt.id

    # req_id 精确过滤也要命中关联表
    r2 = client.get(BASE, params={"req_id": "ZZTOP"}).json()["data"]
    assert r2["total"] == 1


# ────────────────────────── 5. 存量迁移 ──────────────────────────
def test_migration_idempotent(db):
    make_req(db, "LEGACY1", "存量需求")
    opt = make_opt(db, req_id="LEGACY1")

    n1 = active_optimization_service.migrate_legacy_req_ids(db)
    assert n1 == 1
    assert [x.req_id for x in links_of(db, opt.id)] == ["LEGACY1"]
    assert links_of(db, opt.id)[0].req_name == "存量需求"

    n2 = active_optimization_service.migrate_legacy_req_ids(db)
    assert n2 == 0
    assert len(links_of(db, opt.id)) == 1  # 幂等，未重复插入

    # 空 req_id 不迁移
    make_opt(db, title="无关联", req_id="")
    assert active_optimization_service.migrate_legacy_req_ids(db) == 0


# ────────────────────────── 6. 历史列回填（邮件兼容） ──────────────────────────
def test_legacy_column_backfill(client, db):
    for rid in ("X1", "X2"):
        make_req(db, rid)
    opt = make_opt(db)

    client.put(f"{BASE}/{opt.id}/req-links", json={"req_ids": ["X1", "X2"]})
    db.refresh(opt)
    assert opt.req_id == "X1"  # 回填首条，供旧邮件模板使用

    # 清空关联后必须同步清空历史列：否则前端 optReqIds() 会从
    # req_id 回落，复活已删除的文号（2026-10-30 修复「关联需求删不掉」）
    client.put(f"{BASE}/{opt.id}/req-links", json={"req_ids": []})
    db.refresh(opt)
    assert opt.req_id is None

    # 重新关联后历史列恢复回填
    client.put(f"{BASE}/{opt.id}/req-links", json={"req_ids": ["X2"]})
    db.refresh(opt)
    assert opt.req_id == "X2"


def test_email_variables_multi(client, db):
    for rid in ("E1", "E2"):
        make_req(db, rid)
    opt = make_opt(db)
    client.put(f"{BASE}/{opt.id}/req-links", json={"req_ids": ["E1", "E2"]})

    v = active_optimization_service.build_email_variables(db, opt, scene="sync")
    assert v["req_ids"] == ["E1", "E2"]
    assert v["req_id"] == "E1"
    assert v["req_id_text"] == "E1、E2"
