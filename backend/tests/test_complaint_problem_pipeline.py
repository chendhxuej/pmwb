"""D5 编排层回归：全链不依赖人、失败自动退化、自动补跑、dry_run 与发布闸门。

守护的红线（都来自方案 v4.2 §1.3 / §5）：
  1. 语义通道 ``used_llm=False`` 时，那段「规则模板版」绝不能被当成语义结果；
  2. 通道不可用链路照常跑完，逐单标「待自动补跑」并写明缺口，不转人工队列；
  3. dry_run 默认、不写任何业务表；显式落库后未归类清单逐单有缺口原因；
  4. 通道恢复后下一次运行自动补跑，无需人工触发；
  5. 发布闸门真能放行（通道可用 + 描述合规），也能拦截（仅数量闭合达标）；
  6. 金标集只写真实工单号；描述口径变更留旧描述与版本号。
"""
from __future__ import annotations

import json
import re
from datetime import datetime

from sqlalchemy import text

from services.complaint import problem_pipeline as pp

ROWS = (
    ("T1", "客户申请移机，按新地址搜索组网地址无结果，施工单无法生成，无法派单",
     "申请移机时新地址搜索无结果，施工单无法生成"),
    ("T2", "移机新地址查不到组网地址，施工单无法生成，客户无法办理",
     "申请移机时新地址搜索无结果，施工单无法生成"),
    ("T3", "装维已回单，施工结果未回传订单中心，订单停在已派单待回单",
     "查询订单时施工结果未回传，订单停在已派单待回单"),
    ("T4", "施工结果未回传订单中心，订单停在已派单，无法继续办理",
     "查询订单时施工结果未回传，订单停在已派单待回单"),
)
POINTS = {no: pt for no, _, pt in ROWS}


def _seed(db) -> None:
    now = datetime.now()
    for no, content, _ in ROWS:
        db.execute(text(
            "INSERT INTO pmwb_complaint_ticket "
            "(ticket_no, content, solution_history, root_cause, is_batch, is_recur, "
            "created_at, updated_at) VALUES (:n, :c, '', '', 0, 0, :t, :t)"
        ), {"n": no, "c": content, "t": now})
    db.commit()


def fake_channel_up(db, system, user, **kw):
    nos = re.findall(r"单号：(\S+)", user)
    return {"used_llm": True, "provider_name": "fake",
            "text": json.dumps({"results": [{"no": n, "point": POINTS.get(n, "")}
                                            for n in nos]}, ensure_ascii=False)}


def fake_channel_down(db, system, user, **kw):
    # 关键：call_best_available 全失败时会带一段「规则模板版」文本 + used_llm=False
    return {"used_llm": False, "provider_name": None,
            "text": "已生成规则模板版（非 AI 润色）：施工单-未生成",
            "notice": "所有已启用的大模型均不可用，已生成规则模板版（非 AI 润色）。fake: 402"}


def test_channel_down_never_treats_rule_template_as_semantic(db):
    """红线：used_llm=False 时那句模板文本绝不能变成逐单问题点。"""
    _seed(db)
    out = pp.run_full(db, caller=fake_channel_down)
    assert out["channel"]["available"] is False
    assert out["channel"]["calls"] == 1            # 首批失败即停止，不做无谓重试
    assert out["point_ok"] == 0
    assert out["pending_auto_rerun"] == len(ROWS)
    assert out["publish"] is False
    assert any("point_pass_rate" in f for f in out["failed"])
    assert "规则模板版" in out["channel"]["notice"]
    rows = db.execute(text("SELECT point FROM pmwb_complaint_problem_point")).fetchall()
    assert rows == []                              # dry_run 不落库


def test_dry_run_is_default_and_writes_nothing(db):
    _seed(db)
    out = pp.run_full(db, caller=fake_channel_up)
    assert out["dry_run"] is True and out["persisted"] is False
    st = pp.status(db)
    assert st["last_run"] is None
    assert st["counts"]["points"] == 0 and st["counts"]["classes"] == 0


def test_apply_when_channel_down_persists_pending_with_gaps(db):
    _seed(db)
    out = pp.run_full(db, dry_run=False, caller=fake_channel_down)
    assert out["persisted"] is True and out["publish"] is False
    st = pp.status(db)
    assert st["counts"]["points"] == len(ROWS)
    assert st["counts"]["pending_auto_rerun"] == len(ROWS)
    assert st["counts"]["classes"] == 0
    assert st["last_run"]["publish"] is False
    gaps = db.execute(text("SELECT gaps_json FROM pmwb_complaint_problem_gate")).fetchall()
    assert len(gaps) == len(ROWS)
    assert all(json.loads(r[0]) for r in gaps)    # 逐单写明缺什么
    unc = pp.list_unclassified(db)
    assert unc["total"] == len(ROWS)
    assert all(x["gaps"] for x in unc["items"])


def test_auto_rerun_when_channel_returns(db):
    """通道恢复后下一次运行自动补跑，无需人工触发、无需人工确认。"""
    _seed(db)
    pp.run_full(db, dry_run=False, caller=fake_channel_down)
    assert pp.status(db)["counts"]["pending_auto_rerun"] == len(ROWS)
    out = pp.rerun_pending(db, dry_run=False, caller=fake_channel_up)
    assert out["rerun_triggered"] is True
    assert out["pending_before"] == len(ROWS)
    assert out["pending_after"] == 0
    assert out["publish"] is True
    st = pp.status(db)
    assert st["counts"]["point_ok"] == len(ROWS)
    assert st["counts"]["published_classes"] >= 1
    assert st["last_run"]["publish"] is True
    assert st["last_run"]["veto"] == []


def fake_channel_junk(db, system, user, **kw):
    """每单都给出不合格问题点 → 系统自动拒识（已分析但未归类），用于测数量闭合陷阱。"""
    nos = re.findall(r"单号：(\S+)", user)
    return {"used_llm": True, "provider_name": "fake",
            "text": json.dumps({"results": [{"no": n, "point": "其他问题无法处理"}
                                            for n in nos]}, ensure_ascii=False)}


def test_publish_requires_content_closure_not_only_count_closure(db):
    """仅数量闭合达标（全部未归类）必须被闸门拦截，且不发布任何类。"""
    _seed(db)
    out = pp.run_full(db, dry_run=False, caller=fake_channel_junk)
    assert out["publish"] is False
    assert out["metrics"]["count_closure"] == 100.0
    assert out["metrics"]["content_closure"] < 95.0
    assert any("数量闭合达标但内容闭合不达标" in f for f in out["failed"])
    rows = db.execute(text(
        "SELECT status FROM pmwb_complaint_problem_class")).fetchall()
    assert all(r[0] == "blocked" for r in rows)   # 拦截也留痕，但类不可用于汇总


def test_goldset_contains_only_real_ticket_numbers(db):
    _seed(db)
    out = pp.run_full(db, dry_run=False, caller=fake_channel_up)
    assert out["publish"] is True
    nos = {r[0] for r in db.execute(text(
        "SELECT ticket_no FROM pmwb_complaint_problem_goldset")).fetchall()}
    valid = {no for no, _, _ in ROWS}
    assert nos and nos <= valid


def test_description_change_keeps_previous_version(db):
    """§7.3：描述口径变更留旧描述、旧判定卡与版本号，当期标 changed（环比不可比）。"""
    _seed(db)
    payload = {"classes": 1, "unclassified": 0, "pending_auto_rerun": 0}
    def _result(desc):
        return {
            "classes": [{"class_no": "PP-TEST", "description": desc, "elements": {},
                         "card": {"negatives": []}, "fix_point": "", "ticket_cnt": 1,
                         "first_sight": False, "status": "published", "reasons": [],
                         "policy_version": "v4.2-20261104"}],
            "gate": {"pairs": [], "unclassified": []},
            "decision": {"publish": True, "failed": [], "veto": []},
            "goldset": {"core": [], "added": []}, "metrics": {},
        }
    pp._persist(db, points=[], result=_result("申请移机时新地址查不到，施工单无法生成"),
                channel_summary={"available": True}, payload=payload)
    pp._persist(db, points=[], result=_result("申请移机时旧地址字段为空，施工单未触发"),
                channel_summary={"available": True}, payload=payload)
    row = db.execute(text(
        "SELECT version, prev_description, status, prev_card_json "
        "FROM pmwb_complaint_problem_class WHERE class_no = 'PP-TEST'")).fetchone()
    assert row[0] == 2
    assert row[1] == "申请移机时新地址查不到，施工单无法生成"
    assert row[2] == "changed"
    assert row[3] is not None


def test_unparsable_first_batch_stops_immediately(db):
    """护栏：回包格式不对时第一批就停，不能上百批空转烧 token。"""
    from services.complaint.problem_semantic import SemanticPointGenerator
    _seed(db)
    tickets = pp.load_tickets(db)

    def fake_bad(db_, system, user, **kw):
        return {"used_llm": True, "provider_name": "fake", "text": "抱歉我无法完成该任务"}

    ch = SemanticPointGenerator(db, caller=fake_bad, batch_size=10)
    assert ch.prefetch(tickets) is False
    assert ch.calls == 1 and ch.generated == 0
    assert "无法解析" in ch.notice


def test_max_batches_limits_semantic_calls(db):
    """演练护栏：限批后只发指定批数，未覆盖单由编排标待自动补跑。"""
    from services.complaint.problem_semantic import SemanticPointGenerator
    _seed(db)
    tickets = pp.load_tickets(db)
    ch = SemanticPointGenerator(db, caller=fake_channel_up,
                                batch_size=1, max_batches=2)
    assert ch.prefetch(tickets) is True
    assert ch.calls == 2
    assert ch.generated == 2        # 只生成 2 单，其余留给下次自动补跑


def test_http_status_and_run_are_read_only_by_default(client, db):
    """HTTP 入口：默认 dry_run，端点可达且不写库。"""
    _seed(db)
    st = client.get("/api/v1/complaint/problem-v42/status")
    assert st.status_code == 200 and st.json()["code"] == 0
    assert st.json()["data"]["migrated"] is True
    r = client.post("/api/v1/complaint/problem-v42/run", json={})
    assert r.status_code == 200 and r.json()["code"] == 0
    assert r.json()["data"]["dry_run"] is True
    assert r.json()["data"]["persisted"] is False
    cls = client.get("/api/v1/complaint/problem-v42/classes")
    assert cls.status_code == 200 and cls.json()["data"]["total"] == 0
