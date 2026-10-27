"""需求超期风险标记 + 开发天数检索 单测 —— 2026-10-27。

覆盖：
- GET /requirements?dev_days_gt=N：口径 = 开发中(ext.status='dev') + 未上线
  (delivered_date 空 且 开发工单 go_live_date 全空) + stage_log stage='dev' 有 entered_at，
  自然日差**严格大于** N（与 requirement_dev_overdue 同源，禁另造第二份算法）
- 与 status=dev / priority 组合交集
- PUT /requirements/risk-flag/batch：set/clear、ext 自动创建（status 默认 proposed）、
  需求宇宙外 req_id 进 skipped、非法 action 400
- 列表返回 dev_days / ext.overdue_risk / overdue_risk_at / overdue_risk_note

敏感池 R5 联动用例见 test_sensitive_req.py 扩展段。
"""
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient

from db.models import PmwbDevTicket, PmwbRequirementExt, PmwbRequirementStageLog, SentEmail


def _sent(db, req_id, **kw):
    defaults = {
        "req_id": req_id,
        "req_name": f"需求{req_id}",
        "proposer": "张三",
        "propose_time": "2026-07-01",
        "background": "背景",
        "description": "描述",
        "clarification": "澄清",
        "system_name": "测试系统",
        "sa_name": "李四",
        "send_datetime": "2026-07-01",
        "workload": 5.0,
        "is_involved": 1,
        "involve_dev": "是",
    }
    defaults.update(kw)
    obj = SentEmail(**defaults)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def _dev_ext(db, req_id, entered_days_ago=None, priority="P2", **kw):
    """开发中 ext + 可选启动开发时间。"""
    ext = PmwbRequirementExt(req_id=req_id, status="dev", priority=priority, **kw)
    db.add(ext)
    db.commit()
    db.refresh(ext)
    if entered_days_ago is not None:
        log = PmwbRequirementStageLog(
            req_id=req_id, stage="dev", entered_at=datetime.now() - timedelta(days=entered_days_ago)
        )
        db.add(log)
        db.commit()
    return ext


def _list(client, **params):
    resp = client.get("/api/v1/requirements", params=params)
    assert resp.status_code == 200
    return resp.json()["data"]


def _ids(data):
    return {i["req_id"] for i in data["items"]}


# ─────────────────────────────────────────────────────────────
# dev_days_gt 开发天数检索
# ─────────────────────────────────────────────────────────────
def test_dev_days_gt_basic(client: TestClient, db):
    _sent(db, "REQ-DD-1")
    _sent(db, "REQ-DD-2")
    _sent(db, "REQ-DD-3")
    _sent(db, "REQ-DD-4")
    _sent(db, "REQ-DD-5")
    _dev_ext(db, "REQ-DD-1", entered_days_ago=30)  # 命中：开发中 + 30 天
    _dev_ext(db, "REQ-DD-2", entered_days_ago=5)   # 不命中：仅 5 天
    _dev_ext(db, "REQ-DD-3", entered_days_ago=30)
    ext3 = db.query(PmwbRequirementExt).filter_by(req_id="REQ-DD-3").first()
    ext3.status = "accepted"  # 不命中：非开发中
    db.commit()
    _dev_ext(db, "REQ-DD-4", delivered_date=date.today())  # 不命中：已上线
    _dev_ext(db, "REQ-DD-5")  # 不命中：无启动开发时间

    data = _list(client, dev_days_gt=25)
    assert data["total"] == 1
    assert _ids(data) == {"REQ-DD-1"}


def test_dev_days_gt_strict_greater(client: TestClient, db):
    _sent(db, "REQ-ST-1")
    _sent(db, "REQ-ST-2")
    _dev_ext(db, "REQ-ST-1", entered_days_ago=25)  # 恰好 25 天：严格大于不命中
    _dev_ext(db, "REQ-ST-2", entered_days_ago=26)  # 26 天：命中
    data = _list(client, dev_days_gt=25)
    assert _ids(data) == {"REQ-ST-2"}


def test_dev_days_gt_exclude_go_live_ticket(client: TestClient, db):
    """开发工单已有上线日期（未填 delivered_date）→ 未上线判定排除。"""
    _sent(db, "REQ-GL-1")
    _dev_ext(db, "REQ-GL-1", entered_days_ago=30)
    db.add(PmwbDevTicket(
        ticket_no="TK-GL-1", req_id="REQ-GL-1", system_name="测试系统", go_live_date=date.today()
    ))
    db.commit()
    data = _list(client, dev_days_gt=25)
    assert "REQ-GL-1" not in _ids(data)


def test_dev_days_gt_combined_with_status_and_priority(client: TestClient, db):
    _sent(db, "REQ-CM-1")
    _sent(db, "REQ-CM-2")
    _sent(db, "REQ-CM-3")
    _dev_ext(db, "REQ-CM-1", entered_days_ago=30, priority="P0")
    _dev_ext(db, "REQ-CM-2", entered_days_ago=30, priority="P2")
    _dev_ext(db, "REQ-CM-3", entered_days_ago=5, priority="P0")
    # 与 status=dev 组合：day_map 本身隐含 dev，交集即全部超 N 的
    data = _list(client, dev_days_gt=25, status="dev")
    assert _ids(data) == {"REQ-CM-1", "REQ-CM-2"}
    # 再叠加优先级
    data = _list(client, dev_days_gt=25, status="dev", priority="P0")
    assert _ids(data) == {"REQ-CM-1"}


def test_list_returns_dev_days(client: TestClient, db):
    _sent(db, "REQ-DDS-1")
    _dev_ext(db, "REQ-DDS-1", entered_days_ago=30)
    data = _list(client)
    item = next(i for i in data["items"] if i["req_id"] == "REQ-DDS-1")
    assert item["dev_days"] == 30


# ─────────────────────────────────────────────────────────────
# 超期风险标记 risk-flag/batch
# ─────────────────────────────────────────────────────────────
def test_risk_flag_set_and_clear(client: TestClient, db):
    _sent(db, "REQ-RF-1")
    # set：ext 不存在自动创建
    resp = client.put(
        "/api/v1/requirements/risk-flag/batch",
        json={"req_ids": ["REQ-RF-1", "REQ-RF-NOPE"], "action": "set", "note": "重点跟踪"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["updated"] == 1
    assert data["skipped"] == ["REQ-RF-NOPE"]

    ext = db.query(PmwbRequirementExt).filter_by(req_id="REQ-RF-1").first()
    assert ext is not None and ext.overdue_risk == 1
    assert ext.overdue_risk_at is not None
    assert ext.overdue_risk_note == "重点跟踪"
    # ext 自动创建时 status 走默认 proposed（勿污染状态口径）
    assert (ext.status or "proposed") == "proposed"

    # 列表返回标记
    item = next(i for i in _list(client)["items"] if i["req_id"] == "REQ-RF-1")
    assert item["ext"]["overdue_risk"] is True
    assert item["ext"]["overdue_risk_at"] is not None

    # clear：归零清时间，备注保留
    resp = client.put(
        "/api/v1/requirements/risk-flag/batch",
        json={"req_ids": ["REQ-RF-1"], "action": "clear"},
    )
    assert resp.status_code == 200
    db.refresh(ext)
    assert ext.overdue_risk == 0
    assert ext.overdue_risk_at is None
    assert ext.overdue_risk_note == "重点跟踪"
    item = next(i for i in _list(client)["items"] if i["req_id"] == "REQ-RF-1")
    assert item["ext"]["overdue_risk"] is False


def test_risk_flag_batch_dedup_and_single(client: TestClient, db):
    """单个打标 = 传一个 req_id；重复 req_id 去重。"""
    _sent(db, "REQ-RF-2")
    resp = client.put(
        "/api/v1/requirements/risk-flag/batch",
        json={"req_ids": ["REQ-RF-2", "REQ-RF-2"], "action": "set"},
    )
    data = resp.json()["data"]
    assert data["updated"] == 1


def test_risk_flag_invalid_action_400(client: TestClient, db):
    resp = client.put(
        "/api/v1/requirements/risk-flag/batch",
        json={"req_ids": ["REQ-RF-X"], "action": "toggle"},
    )
    assert resp.status_code == 422  # Literal 校验直接拒绝


def test_risk_flag_empty_req_ids_422(client: TestClient, db):
    resp = client.put(
        "/api/v1/requirements/risk-flag/batch",
        json={"req_ids": [], "action": "set"},
    )
    assert resp.status_code == 422
