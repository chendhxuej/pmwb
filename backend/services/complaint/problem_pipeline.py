"""客诉 v4.2 全链编排与持久化（D5-2）——从工单原文到验收闸门，全程无人。

链路：工单原文 → D1 逐单问题点 → D2 问题点类与判定卡 → D3 100% 自动门禁
      → D4 自动验收/发布闸门 → 持久化（dry_run=False 时）。

四条纪律（方案 §1.3，最高约束）：

  - **dry_run 默认**：默认只读演练，不写任何业务表；显式 ``dry_run=False`` 才落库。
  - **失败自动退化**：语义通道不可用时 generator 置 None，D1 自动标
    ``pending_auto_rerun`` 并写明缺口，链路照常跑完、不中断、不猜关键词、不转人工队列。
  - **自动补跑**：每次运行默认增量——只重算「库里没有 ok 结论」和
    ``pending_auto_rerun`` 的单；通道恢复后下一次运行即自动补跑，无需人工触发。
    ``auto_rerun_if_channel_back`` 供导入链/定时器调用，通道仍挂时几乎零成本。
  - **闸门拦截也留痕**：验收不通过时，逐单问题点、未归类清单、验收记录照常持久化，
    但类标 ``blocked``、不写金标集、不发布汇总；不退回人工重判。

跨库安全：全部 SQL 用通用写法（先 SELECT 再 UPDATE/INSERT），不用 ON DUPLICATE KEY /
FIND_IN_SET / FIELD / NOW() 等 MySQL 专有语法——测试库是 SQLite。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from constants import complaint_problem as P
from services.complaint.problem_acceptance import evaluate
from services.complaint.problem_class import build_classes  # noqa: F401（编排层显式依赖）
from services.complaint.problem_gate import run_gate  # noqa: F401
from services.complaint.problem_point import build_point, extract_evidence_spans
from services.complaint.problem_semantic import SemanticPointGenerator

logger = logging.getLogger(__name__)

_POINT_FIELDS = ("point", "status", "gaps", "evidence", "anchors",
                 "old_record_conclusion", "rewritten_from_conclusion",
                 "generator_channel", "judge_channel", "policy_version")


def _j(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def _loads(raw: Any, fallback: Any) -> Any:
    if raw in (None, ""):
        return fallback
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return fallback


def _table_exists(db: Session, name: str) -> bool:
    try:
        db.execute(text(f"SELECT 1 FROM {name} LIMIT 1"))
        return True
    except Exception:  # noqa: BLE001 —— 迁移未执行时优雅降级
        return False


def _upsert(db: Session, table: str, key: str, keyval: Any,
            data: Dict[str, Any]) -> None:
    """通用 upsert（跨 MySQL/SQLite），不依赖数据库专有语法。"""
    hit = db.execute(text(f"SELECT 1 FROM {table} WHERE {key} = :__k"),
                     {"__k": keyval}).fetchone()
    if hit:
        sets = ", ".join(f"{c} = :{c}" for c in data)
        db.execute(text(f"UPDATE {table} SET {sets} WHERE {key} = :__k"),
                   {**data, "__k": keyval})
    else:
        cols = [key] + list(data)
        marks = ", ".join(f":{c}" for c in cols)
        db.execute(text(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({marks})"),
                   {**data, key: keyval})


# ── 读取 ─────────────────────────────────────────────────────────
def load_tickets(db: Session, limit: Optional[int] = None,
                 only_nos: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    sql = ("SELECT ticket_no, content, solution_history, root_cause "
           "FROM pmwb_complaint_ticket ORDER BY id")
    rows = db.execute(text(sql)).fetchall()
    wanted = set(only_nos) if only_nos is not None else None
    out: List[Dict[str, Any]] = []
    for r in rows:
        no = r[0] or ""
        if wanted is not None and no not in wanted:
            continue
        out.append({"ticket_no": no, "content": r[1] or "",
                    "solution_history": r[2] or "", "root_cause": r[3] or ""})
        if limit and len(out) >= int(limit):
            break
    return out


def _load_saved_points(db: Session) -> Dict[str, Dict[str, Any]]:
    """复原已落库的 L1 结论（增量运行复用，避免重复调用语义通道）。"""
    if not _table_exists(db, "pmwb_complaint_problem_point"):
        return {}
    rows = db.execute(text(
        "SELECT ticket_no, point, status, gaps_json, evidence_json, anchors_json, "
        "old_record_conclusion, rewritten_from_conclusion, generator_channel, "
        "judge_channel, policy_version FROM pmwb_complaint_problem_point"
    )).fetchall()
    out: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        out[r[0]] = {
            "ticket_no": r[0], "point": r[1] or "", "status": r[2] or "",
            "gaps": _loads(r[3], []), "evidence": _loads(r[4], []),
            "anchors": _loads(r[5], []),
            "old_record_conclusion": bool(r[6]),
            "rewritten_from_conclusion": bool(r[7]),
            "generator_channel": r[8], "judge_channel": r[9],
            "policy_version": r[10],
        }
    return out


def _channel_fast_check(db: Session) -> Dict[str, Any]:
    """语义通道连通预检（带 TTL 缓存）。挂掉时避免每轮逐个等 HTTP 超时。

    必须做**真实连通探测**而非只看配置或历史错误：通道恢复后要能立刻自动补跑，
    用 last_error 之类的启发式会把刚恢复的通道永远判成不可用。
    """
    try:
        from services.llm_provider import get_status
        st = get_status(db)
        return {"available": bool(st.get("available")),
                "notice": str(st.get("notice") or st.get("error") or "")[:300]}
    except Exception as exc:  # noqa: BLE001 —— 探测异常一律按不可用处理
        return {"available": False, "notice": f"连通探测异常：{str(exc)[:120]}"}


# ── 主链 ─────────────────────────────────────────────────────────
def run_full(db: Session, *, dry_run: bool = True, limit: Optional[int] = None,
             force: bool = False, allow_semantic: bool = True,
             max_semantic_batches: int = 0,
             caller: Optional[Callable[..., Dict[str, Any]]] = None) -> Dict[str, Any]:
    """一键全链。通道不可用时链路照常结束并给出「待自动补跑」清单，绝不中断。

    ``caller`` 仅供单测注入语义通道；生产走 :class:`SemanticPointGenerator`。
    """
    tickets = load_tickets(db, limit=limit)
    saved = {} if force else _load_saved_points(db)
    need = [t for t in tickets
            if force or saved.get(t["ticket_no"], {}).get("status") != "ok"]

    # 注入 caller 时由调用方完全控制通道（单测/演练），跳过连通预检。
    # 生产路径先预检：通道全挂时零语义调用，链路照常毫秒级跑完并标待自动补跑。
    channel = None
    channel_summary = {"channel": "llm-point-v1", "available": False,
                       "notice": "无需调用语义通道（无待分析单或已禁用）",
                       "calls": 0, "generated": 0}
    if allow_semantic and need:
        precheck = None if caller is not None else _channel_fast_check(db)
        if precheck is None or precheck.get("available"):
            channel = SemanticPointGenerator(db, caller=caller,
                                             max_batches=max_semantic_batches)
            evmap = {t["ticket_no"]: extract_evidence_spans(t["content"], t["solution_history"])
                     for t in need}
            channel.prefetch(need, evmap)
            channel_summary = channel.summary()
        else:
            channel_summary = {"channel": "llm-point-v1", "available": False,
                               "provider": None, "calls": 0, "generated": 0,
                               "notice": "连通预检：语义通道不可用（" +
                                         (precheck.get("notice") or "")[:200] + "）",
                               "policy_version": P.POLICY_VERSION}

    generator = channel if (channel is not None and channel.available) else None

    points: List[Dict[str, Any]] = []
    for t in tickets:
        no = t["ticket_no"]
        if not force and saved.get(no, {}).get("status") == "ok":
            points.append(saved[no])
            continue
        r = build_point(t, generator=generator)
        if generator is not None and r["status"] != "ok":
            # 证据不足是永久自动拒识；其余（漏返/未过闸）留待通道恢复后自动补跑
            if P.DEGRADED_REASON_EVIDENCE not in r["gaps"]:
                r["status"] = P.DEGRADED_STATUS
                r["gaps"] = ["语义通道漏返或生成结果未过闸，待自动补跑"] + r["gaps"][:2]
                r["generator_channel"] = None
        points.append(r)

    # 不引入跨批可变状态：每轮对全量 L1 结论重新建类，class_no 由四要素确定性
    # 生成，跨轮稳定；增量只用于避免重复调用语义通道。这样 D4 两次重跑的输入
    # 完全一致（可复现），也不会出现「旧类悄悄扩大描述含义」的漂移。
    # 描述若真变了，由 _persist 的版本留痕保存旧描述与旧判定卡（§7.3）。
    result = evaluate(points)
    decision = result["decision"]
    gate = result["gate"]

    pending = [r["ticket_no"] for r in points if r["status"] == P.DEGRADED_STATUS]
    payload: Dict[str, Any] = {
        "dry_run": bool(dry_run), "publish": bool(decision["publish"]),
        "policy_version": P.POLICY_VERSION,
        "channel": channel_summary,
        "tickets": len(tickets), "recomputed": len(need),
        "point_ok": sum(1 for r in points if r["status"] == "ok"),
        "pending_auto_rerun": len(pending),
        "classes": len(result["classes"]),
        "published_classes": sum(1 for c in result["classes"] if c["status"] == "published"),
        "unclassified": len(gate.get("unclassified", [])),
        "metrics": result["metrics"], "decision": decision,
        "failed": decision["failed"], "veto": decision["veto"],
        "voided_classes": gate.get("voided_classes", []),
        "goldset": result["goldset"],
    }
    if not dry_run:
        _persist(db, points=points, result=result, channel_summary=channel_summary,
                 payload=payload)
        payload["persisted"] = True
        payload["run_no"] = payload.get("run_no")
    else:
        payload["persisted"] = False
    return payload


def _persist(db: Session, *, points: List[Dict[str, Any]], result: Dict[str, Any],
             channel_summary: Dict[str, Any], payload: Dict[str, Any]) -> None:
    """落库：逐单问题点 / 未归类清单 / 类 / 金标集 / 验收批次。"""
    now = datetime.now()
    run_no = "PR-" + now.strftime("%Y%m%d%H%M%S%f")
    publish = bool(result["decision"]["publish"])
    gate = result["gate"]

    for r in points:
        _upsert(db, "pmwb_complaint_problem_point", "ticket_no", r["ticket_no"], {
            "point": r.get("point") or "", "status": r.get("status") or "",
            "gaps_json": _j(r.get("gaps") or []),
            "evidence_json": _j(r.get("evidence") or []),
            "anchors_json": _j(r.get("anchors") or []),
            "old_record_conclusion": 1 if r.get("old_record_conclusion") else 0,
            "rewritten_from_conclusion": 1 if r.get("rewritten_from_conclusion") else 0,
            "generator_channel": r.get("generator_channel"),
            "judge_channel": r.get("judge_channel"),
            "policy_version": r.get("policy_version") or P.POLICY_VERSION,
            "updated_at": now,
        })

    for c in result["classes"]:
        status = c.get("status", "draft") if publish else "blocked"
        desc = c.get("description") or ""
        card_json = _j(c.get("card") or {})
        data: Dict[str, Any] = {
            "description": desc,
            "elements_json": _j(c.get("elements") or {}),
            "card_json": card_json,
            "fix_point": c.get("fix_point") or "",
            "ticket_cnt": int(c.get("ticket_cnt") or 0),
            "first_sight": 1 if c.get("first_sight") else 0,
            "status": status,
            "reasons_json": _j(c.get("reasons") or []),
            "policy_version": c.get("policy_version") or P.POLICY_VERSION,
            "updated_at": now,
        }
        old = db.execute(text(
            "SELECT description, card_json, version FROM pmwb_complaint_problem_class "
            "WHERE class_no = :n"
        ), {"n": c["class_no"]}).fetchone()
        if old is None:
            data["created_at"] = now
            data["version"] = 1
        elif (old[0] or "") != desc:
            # §7.3 描述/判定卡变更 = 口径变更：旧值留痕、版本递增、当期标不可比
            data["version"] = int(old[2] or 1) + 1
            data["prev_description"] = old[0]
            data["prev_card_json"] = old[1]
            data["status"] = "changed"
        _upsert(db, "pmwb_complaint_problem_class", "class_no", c["class_no"], data)

    # 门禁留痕：每单一行；未归类单必须写明缺口（pending 单单独标记供补跑）
    pairs_by_no = {p["ticket_no"]: p for p in gate.get("pairs", [])}
    pending_nos = {r["ticket_no"] for r in points if r["status"] == P.DEGRADED_STATUS}
    for r in points:
        no = r["ticket_no"]
        p = pairs_by_no.get(no)
        if p:
            status, gaps = p["status"], p.get("gaps", [])
            class_no, mapped, missing = p.get("class_no"), p.get("mapped", []), p.get("missing", [])
            judge_ch, second_ch = p.get("judge_channel"), p.get("second_channel")
            gen_ch = p.get("generator_channel")
        else:
            gap_list = next((u.get("gaps", []) for u in gate.get("unclassified", [])
                             if u.get("ticket_no") == no), r.get("gaps", []))
            status = P.DEGRADED_STATUS if no in pending_nos else P.UNCLASSIFIED_STATUS
            gaps, class_no, mapped, missing = gap_list, "", [], []
            judge_ch, second_ch, gen_ch = None, None, r.get("generator_channel")
        _upsert(db, "pmwb_complaint_problem_gate", "ticket_no", no, {
            "class_no": class_no, "status": status,
            "gaps_json": _j(gaps), "mapped_json": _j(mapped), "missing_json": _j(missing),
            "generator_channel": gen_ch, "judge_channel": judge_ch,
            "second_channel": second_ch,
            "policy_version": P.POLICY_VERSION, "updated_at": now,
        })

    if publish:
        # D4 的 goldset.added 里可能混入首现类的类号，只写真实工单号
        valid_nos = {r["ticket_no"] for r in points}
        gold = result.get("goldset", {})
        for no in list(gold.get("core", [])) + list(gold.get("added", [])):
            if no in valid_nos:
                _upsert(db, "pmwb_complaint_problem_goldset", "ticket_no", no, {
                    "source": "auto", "policy_version": P.POLICY_VERSION, "added_at": now,
                })

    db.execute(text(
        "INSERT INTO pmwb_complaint_problem_run "
        "(run_no, dry_run, publish, failed_json, veto_json, metrics_json, "
        "classes_cnt, unclassified_cnt, pending_cnt, channel_available, "
        "channel_notice, policy_version, created_at) "
        "VALUES (:run_no, :dry_run, :publish, :failed_json, :veto_json, :metrics_json, "
        ":classes_cnt, :unclassified_cnt, :pending_cnt, :channel_available, "
        ":channel_notice, :policy_version, :created_at)"
    ), {
        "run_no": run_no, "dry_run": 0, "publish": 1 if publish else 0,
        "failed_json": _j(result["decision"]["failed"]),
        "veto_json": _j(result["decision"]["veto"]),
        "metrics_json": _j(result["metrics"]),
        "classes_cnt": payload["classes"], "unclassified_cnt": payload["unclassified"],
        "pending_cnt": payload["pending_auto_rerun"],
        "channel_available": 1 if channel_summary.get("available") else 0,
        "channel_notice": (channel_summary.get("notice") or "")[:500],
        "policy_version": P.POLICY_VERSION, "created_at": now,
    })
    db.commit()
    payload["run_no"] = run_no


# ── 自动补跑 ─────────────────────────────────────────────────────
def rerun_pending(db: Session, *, dry_run: bool = True,
                  caller: Optional[Callable[..., Dict[str, Any]]] = None) -> Dict[str, Any]:
    """对「待自动补跑」单重新跑全链；通道仍不可用时原样保留，不中断、不排队等人。"""
    before = _pending_count(db)
    out = run_full(db, dry_run=dry_run, allow_semantic=True, caller=caller)
    out["pending_before"] = before
    out["pending_after"] = out["pending_auto_rerun"]
    out["rerun_triggered"] = bool(before)
    return out


def auto_rerun_if_channel_back(db: Session) -> Dict[str, Any]:
    """供导入链/定时器调用：通道恢复且有待补跑单时自动补跑；否则零成本返回。

    用 ``llm_provider.get_status`` 的带缓存连通探测做快速判断，避免通道仍挂时
    每次导入都触发一次昂贵的语义调用。
    """
    if _pending_count(db) <= 0:
        return {"triggered": False, "reason": "无待自动补跑单"}
    st = _channel_fast_check(db)
    if not st.get("available"):
        return {"triggered": False, "reason": "语义通道仍不可用，待自动补跑单原样保留",
                "pending": _pending_count(db)}
    out = run_full(db, dry_run=False)
    return {"triggered": True, "publish": out["publish"],
            "pending_before": out["pending_auto_rerun"],
            "run_no": out.get("run_no")}


def _pending_count(db: Session) -> int:
    if not _table_exists(db, "pmwb_complaint_problem_point"):
        return 0
    return int(db.execute(text(
        "SELECT COUNT(*) FROM pmwb_complaint_problem_point WHERE status = :s"
    ), {"s": P.DEGRADED_STATUS}).scalar() or 0)


# ── 查询（供 HTTP / CLI / D6 前端）────────────────────────────────
def status(db: Session) -> Dict[str, Any]:
    if not _table_exists(db, "pmwb_complaint_problem_run"):
        return {"migrated": False, "policy_version": P.POLICY_VERSION,
                "hint": "未检测到 v4.2 持久化表，请先执行 alembic upgrade 20261104000008"}
    row = db.execute(text(
        "SELECT run_no, publish, failed_json, veto_json, metrics_json, classes_cnt, "
        "unclassified_cnt, pending_cnt, channel_available, channel_notice, created_at "
        "FROM pmwb_complaint_problem_run ORDER BY id DESC LIMIT 1"
    )).fetchone()
    counts = {
        "points": int(db.execute(text("SELECT COUNT(*) FROM pmwb_complaint_problem_point")).scalar() or 0),
        "point_ok": int(db.execute(text(
            "SELECT COUNT(*) FROM pmwb_complaint_problem_point WHERE status = 'ok'")).scalar() or 0),
        "classes": int(db.execute(text("SELECT COUNT(*) FROM pmwb_complaint_problem_class")).scalar() or 0),
        "published_classes": int(db.execute(text(
            "SELECT COUNT(*) FROM pmwb_complaint_problem_class WHERE status = 'published'")).scalar() or 0),
        "blocked_classes": int(db.execute(text(
            "SELECT COUNT(*) FROM pmwb_complaint_problem_class WHERE status = 'blocked'")).scalar() or 0),
        "unclassified": int(db.execute(text(
            "SELECT COUNT(*) FROM pmwb_complaint_problem_gate WHERE status = 'unclassified'")).scalar() or 0),
        "pending_auto_rerun": _pending_count(db),
        "goldset": int(db.execute(text(
            "SELECT COUNT(*) FROM pmwb_complaint_problem_goldset")).scalar() or 0),
    }
    last = None
    if row:
        last = {"run_no": row[0], "publish": bool(row[1]), "failed": _loads(row[2], []),
                "veto": _loads(row[3], []), "metrics": _loads(row[4], {}),
                "classes_cnt": row[5], "unclassified_cnt": row[6], "pending_cnt": row[7],
                "channel_available": bool(row[8]), "channel_notice": row[9],
                "created_at": str(row[10] or "")}
    return {"migrated": True, "policy_version": P.POLICY_VERSION,
            "last_run": last, "counts": counts}


def list_classes(db: Session, *, status_filter: str = "", keyword: str = "",
                 page: int = 1, page_size: int = 20) -> Dict[str, Any]:
    if not _table_exists(db, "pmwb_complaint_problem_class"):
        return {"total": 0, "items": []}
    rows = db.execute(text(
        "SELECT class_no, description, ticket_cnt, first_sight, status, "
        "fix_point, card_json, elements_json, reasons_json FROM pmwb_complaint_problem_class "
        "ORDER BY ticket_cnt DESC, class_no ASC"
    )).fetchall()
    items = [{
        "class_no": r[0], "description": r[1], "ticket_cnt": r[2] or 0,
        "first_sight": bool(r[3]), "status": r[4], "fix_point": r[5] or "",
        "card": _loads(r[6], {}), "elements": _loads(r[7], {}),
        "reasons": _loads(r[8], []),
    } for r in rows]
    if status_filter:
        items = [x for x in items if x["status"] == status_filter]
    if keyword:
        items = [x for x in items if keyword in (x["description"] or "")]
    total = len(items)
    start = (max(1, int(page)) - 1) * max(1, int(page_size))
    return {"total": total, "page": int(page), "page_size": int(page_size),
            "items": items[start:start + max(1, int(page_size))]}


def list_unclassified(db: Session, *, reason: str = "", page: int = 1,
                      page_size: int = 20) -> Dict[str, Any]:
    if not _table_exists(db, "pmwb_complaint_problem_gate"):
        return {"total": 0, "items": []}
    rows = db.execute(text(
        "SELECT ticket_no, status, class_no, gaps_json FROM pmwb_complaint_problem_gate "
        "WHERE status <> 'matched' AND status <> 'matched_second' ORDER BY ticket_no"
    )).fetchall()
    items = []
    for r in rows:
        gaps = _loads(r[3], [])
        if reason and reason not in " ".join(gaps):
            continue
        items.append({"ticket_no": r[0], "status": r[1], "class_no": r[2] or "",
                      "gaps": gaps, "reason": "；".join(gaps)})
    total = len(items)
    start = (max(1, int(page)) - 1) * max(1, int(page_size))
    return {"total": total, "page": int(page), "page_size": int(page_size),
            "items": items[start:start + max(1, int(page_size))]}
