"""客诉根因库（L2 根因簇）—— 自下而上归纳、人工确认入库、命中复用。

为什么需要它（与 rootcause.py 的分工）：
  rootcause.py 解决「每单说清真实问题」（L1 最小事实单元）；
  但同一类问题在不同工单里措辞各异（「HDC 校验不通过」/「电视激活提示未开通」/
  「无电视开通单」），不做归并就无法统计「这类问题一共多少单、修一处能消掉多少」。
  本模块把 L1 根因收敛成簇（L2），是批量投诉识别与解决方案落点的**唯一抓手**。

核心机制（老大 2026-11-03 拍板「自下而上归纳」）：
  1. 不做预设根因树，从真实工单根因里聚出来——避免一开始就把架子定错；
  2. 先匹配库内已有簇（open + candidate 都参与匹配），命中即复用 → 口径统一、可聚合；
  3. 未命中才提新候选簇（status=candidate），人工确认后才 open；
  4. 同义簇用 merge 合并，工单指针统一改指主簇，不删历史；
  5. 库内代表单回流作 few-shot（见 rootcause.load_few_shots），越用越准。

写入边界：pmwb_complaint_ticket.rootcause_no 的**唯一写入点**是本模块 assign/build_clusters。
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from constants import complaint_rootcause as RC
from services.complaint import config as C
from services.complaint.llm_classify import _extract_json
from services.llm_provider import call_best_available

logger = logging.getLogger(__name__)

CLUSTER_BATCH = 20          # 每批送 LLM 归并的根因条数
LIB_IN_PROMPT_MAX = 60      # prompt 中展示的库内簇上限（控 token）

# 桶内归并（主动分组）—— 2026-11-03 重构说明：
#   原先「逐条判定归入哪个已有簇 / 或 NEW」在实测中退化成 1 单 1 簇（228 单 → 140 簇）：
#   每条根因都带不同的单号账号，模型逐条看就都觉得「机制不同」，且天然倾向 NEW。
#   改为「先按 系统+环节 分桶，再让模型在桶内主动分组」——一次看到全桶样本，
#   分组是全局视角，能自然收敛成「同对象同机制」的簇。
_CLUSTER_PROMPT = (
    "你是电信运营商政企/商客业务客诉根因归并专家。下面给出同一个「系统 + 故障环节」桶内的"
    "若干条工单根因，请把它们**分组**成尽可能少的根因簇。\n"
    "分组标准（重要）：同一簇内必须是「同一个缺陷对象 + 同一套失败机制」；"
    "仅仅因为具体单号、账号、客户名、日期不同而措辞有差异的，属于**同一个簇**，不得拆开。\n"
    "例：以下三条应归一簇——\n"
    "  「电视账号 A 激活校验返回未开通，机顶盒开通单未下发」\n"
    "  「电视账号 B 提示未开通，无电视开通单」\n"
    "  「电视账号 C 激活校验失败，机顶盒开通单缺失」\n"
    "  → 簇：机顶盒开通单未下发致电视激活校验不通过\n"
    "反之，若失败机制不同（一个是开通单未下发、一个是账号密码错），必须分属不同簇。\n"
    "簇标题规范：{缺陷对象}-{失败机制}，10~30 字，不用「异常/问题/失败」等空词，"
    "不重复系统名与环节名（外层已标明）。\n"
    "必须覆盖给出的全部工单，不能漏。\n"
    "输出仅 JSON："
    '{"clusters": [{"title": "...", "description": "判定边界一句话", '
    '"members": ["工单号", "..."]}]}'
)

def _next_rc_no(db: Session) -> str:
    row = db.execute(text(
        "SELECT rootcause_no FROM pmwb_complaint_rootcause "
        "WHERE rootcause_no LIKE 'RC-%' ORDER BY id DESC LIMIT 1"
    )).scalar()
    seq = 1
    if row:
        try:
            seq = int(str(row).split("-")[-1]) + 1
        except ValueError:
            seq = 1
    return f"RC-{seq:04d}"


def load_lib(db: Session, statuses: tuple = (RC.RC_LIB_OPEN, RC.RC_LIB_CANDIDATE),
             limit: int = LIB_IN_PROMPT_MAX) -> List[Dict[str, Any]]:
    """库内可匹配的簇（按单量降序，控数量走 LIB_IN_PROMPT_MAX）。"""
    if not statuses:
        return []
    marks = ",".join(f"'{s}'" for s in statuses)
    rows = db.execute(text(
        "SELECT rootcause_no, title, description, fault_system, fault_stage, "
        "fault_type, status, ticket_cnt FROM pmwb_complaint_rootcause "
        f"WHERE status IN ({marks}) ORDER BY ticket_cnt DESC, id ASC LIMIT :n"
    ), {"n": int(limit)}).fetchall()
    return [{"rc_no": r[0], "title": r[1], "description": r[2] or "", "fault_system": r[3],
             "fault_stage": r[4], "fault_type": r[5], "status": r[6], "ticket_cnt": r[7]}
            for r in rows]


def _tickets_to_group(db: Session, limit: Optional[int]) -> List[Dict[str, Any]]:
    lim = f" LIMIT {int(limit)}" if limit else ""
    rows = db.execute(text(
        "SELECT ticket_no, root_cause, fault_system, fault_stage, fault_type, rc_status, week "
        "FROM pmwb_complaint_ticket "
        "WHERE root_cause IS NOT NULL AND root_cause != '' "
        "AND (rootcause_no IS NULL OR rootcause_no = '') "
        f"ORDER BY rc_status DESC, fault_system ASC, fault_stage ASC, id ASC{lim}"
    )).fetchall()
    return [{"ticket_no": r[0], "root_cause": r[1], "fault_system": r[2],
             "fault_stage": r[3], "fault_type": r[4], "rc_status": r[5], "week": r[6]}
            for r in rows]


def _create_cluster(db: Session, title: str, description: str,
                    tickets: List[Dict[str, Any]], key: Optional[tuple] = None) -> str:
    """新建候选簇（同标题复用已有簇，保证增量归并口径一致）。"""
    title = title.strip()[:200]
    if not title:
        return ""
    exist = db.execute(text(
        "SELECT rootcause_no FROM pmwb_complaint_rootcause WHERE title = :t LIMIT 1"
    ), {"t": title}).scalar()
    if exist:
        return exist
    no = _next_rc_no(db)
    first = tickets[0] if tickets else {}
    cnt = Counter(t.get("fault_system") or "" for t in tickets).most_common(1)
    stage = Counter(t.get("fault_stage") or "" for t in tickets).most_common(1)
    ftype = Counter(t.get("fault_type") or "" for t in tickets).most_common(1)
    db.execute(text(
        "INSERT INTO pmwb_complaint_rootcause "
        "(rootcause_no, title, description, fault_system, fault_stage, fault_type, "
        " status, source, ticket_cnt, sample_tickets, first_week, last_week, "
        " created_at, updated_at) "
        "VALUES (:no, :title, :desc, :sys, :stage, :ftype, 'candidate', 'ai', 0, :samples, "
        " :wk, :wk, :ts, :ts)"
    ), {"no": no, "title": title, "desc": (description or "").strip()[:500],
        "sys": cnt[0][0] if cnt else "", "stage": stage[0][0] if stage else "",
        "ftype": ftype[0][0] if ftype else "",
        "samples": json.dumps([t["ticket_no"] for t in tickets[:8]], ensure_ascii=False),
        "wk": first.get("week") or "", "ts": datetime.now()})
    return no


def _point(db: Session, ticket_no: str, rc_no: str) -> None:
    db.execute(text(
        "UPDATE pmwb_complaint_ticket SET rootcause_no = :rc WHERE ticket_no = :no"
    ), {"rc": rc_no, "no": ticket_no})


def _existing_titles(db: Session, key: tuple) -> List[str]:
    """该桶已有的簇标题（去前缀），供桶内分组复用，保证增量不重复造簇。"""
    sys_name, stage = key
    prefix = f"{sys_name}-{stage}-"
    try:
        rows = db.execute(text(
            "SELECT title FROM pmwb_complaint_rootcause "
            "WHERE status IN ('open', 'candidate') AND title LIKE :p ORDER BY ticket_cnt DESC LIMIT 20"
        ), {"p": prefix + "%"}).fetchall()
    except Exception:  # noqa: BLE001
        return []
    return [r[0][len(prefix):] for r in rows if r[0].startswith(prefix)]


_MERGE_PROMPT = (
    "你是客诉根因库的治理专家。下面列出根因库中已有的簇（编号｜系统｜环节｜单量｜标题），"
    "其中存在「同一个缺陷机制被拆成多个簇」的重复（因为单条工单的系统/环节判定不一致，"
    "同一问题可能落在不同桶里）。请找出这些重复簇，给出合并方案。\n"
    "合并判据：缺陷对象相同 **且** 失败机制相同（例：「CRM 开通后电视账号未同步至电视平台」"
    "与「电视账号开通数据 CRM 未同步至电视平台」是同一个，必须合并）。\n"
    "注意：机制不同不得合并（「开通单未下发」≠「账号数据未同步」，虽然现象都是激活失败）。\n"
    "合并方向：保留单量最大的簇，其余并入；需要改标题时给 new_title（{对象}-{机制}）。\n"
    "输出仅 JSON："
    '{"groups": [{"keep": "RC-0001", "absorb": ["RC-0005", "RC-0009"], '
    '"new_title": "可选，保留簇的新标题"}]}'
)


def auto_merge_similar(db: Session, limit_groups: int = 200) -> Dict[str, Any]:
    """全局簇归并（跨桶消重）——桶内分组的必要收尾。

    为什么需要：桶是按「AI 判定的系统+环节」分的，而这两个标签单条判定不稳定，
    同类问题会被拆到不同桶（实测：电视账号未同步被拆成 4 个簇、合计 28 单）。
    本函数在簇标题层做二次归并，把「同对象同机制」的簇收敛成一个。
    """
    clusters = db.execute(text(
        "SELECT rootcause_no, title, fault_system, fault_stage, ticket_cnt "
        "FROM pmwb_complaint_rootcause WHERE status IN ('open','candidate') "
        "ORDER BY ticket_cnt DESC, id ASC LIMIT :n"
    ), {"n": int(limit_groups)}).fetchall()
    if len(clusters) < 2:
        return {"scanned": len(clusters), "merged": 0, "groups": [], "used_llm": False,
                "notice": "簇太少，无需归并"}

    lines = [f"- {r[0]}｜{r[2] or '?'}｜{r[3] or '?'}｜{r[4]} 单｜{r[1]}" for r in clusters]
    user = "【根因库簇清单】\n" + "\n".join(lines) + (
        f"\n\n请输出合并方案（最多 {len(clusters)} 个簇，只输出真正需要合并的分组）。")
    res = call_best_available(db, _MERGE_PROMPT, user, max_tokens=4000, timeout=300)
    if not res.get("used_llm"):
        return {"scanned": len(clusters), "merged": 0, "groups": [], "used_llm": False,
                "notice": res.get("notice") or "大模型不可用"}

    data = _extract_json(res.get("text") or "") or {}
    valid = {r[0] for r in clusters}
    done: List[Dict[str, Any]] = []
    merged = 0
    for g in (data.get("groups") or []):
        if not isinstance(g, dict):
            continue
        keep = str(g.get("keep") or "").strip()
        if keep not in valid:
            continue
        new_title = str(g.get("new_title") or "").strip()
        if new_title:
            db.execute(text(
                "UPDATE pmwb_complaint_rootcause SET title = :t, updated_at = :ts "
                "WHERE rootcause_no = :no"), {"t": new_title[:200], "no": keep, "ts": datetime.now()})
        for src in (g.get("absorb") or []):
            src = str(src).strip()
            if src not in valid or src == keep:
                continue
            r = merge(db, src, keep)
            if r.get("ok"):
                merged += int(r.get("moved") or 0)
        done.append({"keep": keep, "absorb": g.get("absorb") or []})
    # 不重算簇级标签：人工确认时校正过的 fault_* 是资产，合并后按众数覆盖会丢
    refresh_counts(db, update_labels=False)
    return {"scanned": len(clusters), "merged": merged, "groups": done,
            "used_llm": True, "notice": f"归并完成，合并 {len(done)} 组"}


def _bucket_prompt(key: tuple, tickets: List[Dict[str, Any]],
                   existing: Optional[List[str]] = None) -> str:
    sys_name, stage = key
    parts = [f"【桶】系统={sys_name}｜故障环节={stage}｜共 {len(tickets)} 单"]
    if existing:
        parts.append("【该桶已有根因簇（同机制的请直接沿用下列标题，不要另造近义名）】")
        parts.extend(f"- {t}" for t in existing)
    parts.append("\n【根因列表】")
    for t in tickets:
        parts.append(f'工单 {t["ticket_no"]}（{t.get("fault_type") or "?"}）：{t.get("root_cause") or ""}')
    parts.append("\n请分组并输出 JSON（clusters 数组，必须覆盖全部工单号）。")
    return "\n".join(parts)


def _group_bucket(db: Session, key: tuple, tickets: List[Dict[str, Any]]
                  ) -> Tuple[List[Tuple[str, str, List[Dict[str, Any]]]], int]:
    """桶内主动分组：返回 ([(簇标题, 判定边界, 成员工单)], 失败数)。

    LLM 不可用或漏单时，剩余工单按「单条成簇」兜底（不丢数据）。
    """
    sys_name, stage = key
    existing = _existing_titles(db, key)
    groups: List[Tuple[str, str, List[Dict[str, Any]]]] = []
    failed = 0
    for i in range(0, len(tickets), CLUSTER_BATCH):
        chunk = tickets[i:i + CLUSTER_BATCH]
        if len(chunk) == 1:
            t = chunk[0]
            groups.append((_short_title(t), "", [t]))
            continue
        res = call_best_available(db, _CLUSTER_PROMPT,
                                  _bucket_prompt(key, chunk, existing),
                                  max_tokens=4000, timeout=300)
        if not res.get("used_llm"):
            failed += len(chunk)
            for t in chunk:
                groups.append((_short_title(t), "", [t]))
            continue
        data = _extract_json(res.get("text") or "") or {}
        by_no = {t["ticket_no"]: t for t in chunk}
        covered: set = set()
        for c in (data.get("clusters") or []):
            if not isinstance(c, dict):
                continue
            title = str(c.get("title") or "").strip()
            members = [str(m).strip() for m in (c.get("members") or [])]
            ts = [by_no[m] for m in members if m in by_no and m not in covered]
            if not title or not ts:
                continue
            covered.update(members)
            groups.append((title[:120], str(c.get("description") or "").strip()[:500], ts))
        # 漏单兜底
        for t in chunk:
            if t["ticket_no"] not in covered:
                groups.append((_short_title(t), "", [t]))
    return groups, failed


def _short_title(t: Dict[str, Any]) -> str:
    """单条成簇时从根因提炼短标题（去掉开头单号类噪音，截 40 字）。"""
    cause = (t.get("root_cause") or "").strip()
    cause = re.sub(r"^[\d\s,，、./:-]{6,}", "", cause)
    return (cause[:40] or t["ticket_no"])


def build_clusters(db: Session, limit: Optional[int] = None) -> Dict[str, Any]:
    """把未归属的 L1 根因归并进根因库（新簇先落 candidate，人工确认后 open）。

    两步走：
      ① 规则分桶：按 fault_system + fault_stage 分桶（同系统同环节才可能同机制）；
      ② 桶内主动分组：LLM 一次看全桶样本，按「缺陷对象 + 失败机制」打成若干簇。
    这样既避免跨系统乱并，也避免逐条判定的「全都 NEW」退化。
    """
    pending = _tickets_to_group(db, limit)
    if not pending:
        return {"scanned": 0, "assigned": 0, "new_clusters": [], "failed": 0,
                "used_llm": False, "notice": "没有待归并的根因"}

    buckets: Dict[tuple, List[Dict[str, Any]]] = {}
    for t in pending:
        key = ((t.get("fault_system") or "").strip() or "未标注",
               (t.get("fault_stage") or "").strip() or "未标注")
        buckets.setdefault(key, []).append(t)

    assigned = failed = 0
    new_clusters: List[str] = []
    used_llm = False
    notice = ""

    # 大桶先处理（主题优先），小桶后处理
    for key in sorted(buckets.keys(), key=lambda k: -len(buckets[k])):
        ts = buckets[key]
        groups, bad = _group_bucket(db, key, ts)
        failed += bad
        used_llm = used_llm or (bad < len(ts))
        for title, desc, members in groups:
            full_title = f"{key[0]}-{key[1]}-{title}"[:200]
            rc_no = _create_cluster(db, full_title, desc, members, key)
            if not rc_no:
                failed += len(members)
                continue
            for t in members:
                _point(db, t["ticket_no"], rc_no)
                assigned += 1
            if rc_no not in new_clusters:
                new_clusters.append(rc_no)
        db.commit()

    refresh_counts(db, update_labels=True)
    return {
        "scanned": len(pending), "assigned": assigned, "failed": failed,
        "new_clusters": new_clusters, "buckets": len(buckets), "used_llm": used_llm,
        "notice": notice or ("根因归并完成" if used_llm else "大模型不可用，未做归并"),
    }


def refresh_counts(db: Session, commit: bool = True,
                   update_labels: bool = False) -> Dict[str, Any]:
    """重算簇统计（单量、首见/最近周、代表单）。

    派生值一律重算，不做增量累加——避免重复归并/合并后数据漂移。
    簇级标签（fault_*）默认**不覆盖**：人工确认时校正过的标签是资产，
    需要按众数重算时显式传 update_labels=True。
    """
    db.execute(text(
        "UPDATE pmwb_complaint_rootcause SET ticket_cnt = 0, sample_tickets = '[]'"))
    # 跨库注意：禁 SUBSTRING_INDEX/FIND_IN_SET 等 MySQL 专有函数（测试库 SQLite）。
    # 代表单取「簇内 id 最小前 8」——按 id 升序在 Python 侧截断，不用 GROUP_CONCAT ORDER BY。
    rows = db.execute(text(
        "SELECT rootcause_no, COUNT(*), MIN(week), MAX(week), "
        "  GROUP_CONCAT(fault_stage), GROUP_CONCAT(fault_type), "
        "  GROUP_CONCAT(own_party), GROUP_CONCAT(fix_mode) "
        "FROM pmwb_complaint_ticket WHERE rootcause_no IS NOT NULL AND rootcause_no != '' "
        "GROUP BY rootcause_no"
    )).fetchall()
    sample_rows = db.execute(text(
        "SELECT rootcause_no, ticket_no FROM pmwb_complaint_ticket "
        "WHERE rootcause_no IS NOT NULL AND rootcause_no != '' ORDER BY id ASC"
    )).fetchall()
    samples_map: Dict[str, List[str]] = {}
    for rc_no, tno in sample_rows:
        lst = samples_map.setdefault(rc_no, [])
        if len(lst) < 8:
            lst.append(tno)

    def _mode(raw: Optional[str]) -> str:
        if not raw:
            return ""
        vals = [v for v in str(raw).split(",") if v]
        return Counter(vals).most_common(1)[0][0] if vals else ""

    for rc_no, cnt, fw, lw, stages, ftypes, parties, fixes in rows:
        sets = ["ticket_cnt = :c", "first_week = :fw", "last_week = :lw",
                "sample_tickets = :s", "updated_at = :ts"]
        params: Dict[str, Any] = {
            "c": int(cnt), "fw": fw or "", "lw": lw or "",
            "s": json.dumps(samples_map.get(rc_no) or [], ensure_ascii=False),
            "no": rc_no, "ts": datetime.now()}
        if update_labels:
            sets += ["fault_stage = :stage", "fault_type = :ftype",
                     "own_party = :party", "fix_mode = :fix"]
            params.update({"stage": _mode(stages), "ftype": _mode(ftypes),
                           "party": _mode(parties), "fix": _mode(fixes)})
        db.execute(text(
            f"UPDATE pmwb_complaint_rootcause SET {', '.join(sets)} WHERE rootcause_no = :no"
        ), params)
    if commit:
        db.commit()
    return {"clusters": len(rows)}


# ── 人工操作 ─────────────────────────────────────────────────
def confirm(db: Session, rc_no: str, title: Optional[str] = None,
            description: Optional[str] = None,
            fault_type: Optional[str] = None, own_party: Optional[str] = None,
            fix_mode: Optional[str] = None) -> Dict[str, Any]:
    """候选簇人工确认入账（可同时改名/补边界说明/校正标签）。"""
    row = db.execute(text(
        "SELECT id, title FROM pmwb_complaint_rootcause WHERE rootcause_no = :no"
    ), {"no": rc_no}).first()
    if not row:
        return {"ok": False, "message": "根因簇不存在"}
    sets = ["status = 'open'", "updated_at = :ts"]
    params: Dict[str, Any] = {"no": rc_no, "ts": datetime.now()}
    if title and title.strip():
        sets.append("title = :title")
        params["title"] = title.strip()[:200]
    if description is not None:
        sets.append("description = :desc")
        params["desc"] = (description or "").strip()[:500]
    if fault_type and fault_type in RC.FAULT_TYPES:
        sets.append("fault_type = :ftype")
        params["ftype"] = fault_type
    if own_party and own_party in RC.OWN_PARTIES:
        sets.append("own_party = :party")
        params["party"] = own_party
    if fix_mode and fix_mode in RC.FIX_MODES:
        sets.append("fix_mode = :fix")
        params["fix"] = fix_mode
    db.execute(text(
        f"UPDATE pmwb_complaint_rootcause SET {', '.join(sets)} WHERE rootcause_no = :no"
    ), params)
    db.commit()
    return {"ok": True, "rootcause_no": rc_no}


def resolve_merged_no(db: Session, rc_no: str) -> str:
    """沿 merged_to 链追到终簇（消重后旧簇号一律解析到存活簇，防悬空锚点）。"""
    seen = set()
    cur = (rc_no or "").strip()
    while cur and cur not in seen:
        seen.add(cur)
        nxt = db.execute(text(
            "SELECT merged_to FROM pmwb_complaint_rootcause WHERE rootcause_no = :n"
        ), {"n": cur}).scalar()
        if not nxt:
            break
        cur = nxt
    return cur or (rc_no or "")


def sync_entity_anchors(db: Session) -> Dict[str, int]:
    """问题台账/措施的簇锚跟随消重迁移（merge 收尾；也可单独跑一次修复）。

    为什么必须：auto_merge_similar 会把同义簇并进主簇（源簇置 merged、工单指针
    迁走），但问题台账 rootcause_no/rootcause_nos 与措施 rootcause_nos 若仍锚着
    源簇，已知判定（known.py 走「工单簇 → 在办问题簇」匹配）会全量失配——
    2026-11-04 实测：CPB-2026W42-01 锚 RC-0060 被并入 RC-0059 后已知率掉到 0。
    问题/措施表都在百级以内，直接全量读出在 Python 侧做列表替换（跨库安全，
    禁 FIND_IN_SET）。
    """
    remapped_problems = remapped_actions = 0
    problems = db.execute(text(
        "SELECT id, rootcause_no, rootcause_nos FROM pmwb_complaint_problem"
    )).fetchall()
    for pid, rc, rcs in problems:
        new_rc = resolve_merged_no(db, rc) if rc else rc
        lst = [x.strip() for x in (rcs or "").split(",") if x.strip()]
        new_lst = [resolve_merged_no(db, x) for x in lst]
        # 去重保序；主簇若在列表里保持首位
        merged_list = list(dict.fromkeys(
            ([new_rc] if new_rc else []) + new_lst))
        new_nos = ",".join(merged_list) if lst or new_rc else ""
        if new_rc != (rc or "") or new_nos != (rcs or ""):
            db.execute(text(
                "UPDATE pmwb_complaint_problem SET rootcause_no = :rc, "
                "rootcause_nos = :ns WHERE id = :i"
            ), {"rc": new_rc, "ns": new_nos, "i": pid})
            remapped_problems += 1

    actions = db.execute(text(
        "SELECT id, rootcause_nos FROM pmwb_complaint_action "
        "WHERE rootcause_nos IS NOT NULL AND rootcause_nos <> ''"
    )).fetchall()
    for aid, rcs in actions:
        lst = [x.strip() for x in (rcs or "").split(",") if x.strip()]
        new_lst = [resolve_merged_no(db, x) for x in lst]
        new_nos = ",".join(dict.fromkeys(new_lst))
        if new_nos != (rcs or ""):
            db.execute(text(
                "UPDATE pmwb_complaint_action SET rootcause_nos = :ns WHERE id = :i"
            ), {"ns": new_nos, "i": aid})
            remapped_actions += 1
    return {"problems": remapped_problems, "actions": remapped_actions}


def merge(db: Session, src_no: str, dst_no: str) -> Dict[str, Any]:
    """同义簇合并：工单指针统一改指主簇，源簇置 merged（不删历史）。

    收尾必须同步迁移问题台账/措施的簇锚（sync_entity_anchors），否则
    在办问题锚着已消亡簇会导致已知判定全量失配。
    """
    if src_no == dst_no:
        return {"ok": False, "message": "不能与自身合并"}
    dst = db.execute(text(
        "SELECT id FROM pmwb_complaint_rootcause WHERE rootcause_no = :no"
    ), {"no": dst_no}).first()
    if not dst:
        return {"ok": False, "message": "主簇不存在"}
    moved = db.execute(text(
        "UPDATE pmwb_complaint_ticket SET rootcause_no = :dst WHERE rootcause_no = :src"
    ), {"dst": dst_no, "src": src_no}).rowcount
    db.execute(text(
        "UPDATE pmwb_complaint_rootcause SET status = 'merged', merged_to = :dst, "
        "ticket_cnt = 0, updated_at = :ts WHERE rootcause_no = :src"
    ), {"dst": dst_no, "src": src_no, "ts": datetime.now()})
    sync_entity_anchors(db)
    db.commit()
    refresh_counts(db)
    return {"ok": True, "moved": int(moved or 0), "merged_into": dst_no}


def disable(db: Session, rc_no: str, reopen: bool = False) -> Dict[str, Any]:
    """停用/恢复簇（停用后不再参与匹配，存量工单指针保留）。"""
    status = RC.RC_LIB_OPEN if reopen else RC.RC_LIB_DISABLED
    db.execute(text(
        "UPDATE pmwb_complaint_rootcause SET status = :st, updated_at = :ts "
        "WHERE rootcause_no = :no"
    ), {"st": status, "no": rc_no, "ts": datetime.now()})
    db.commit()
    return {"ok": True, "status": status}


def assign_manual(db: Session, ticket_no: str, rc_no: str) -> Dict[str, Any]:
    """人工改单归属根因簇（人工指定优先，重跑 build_clusters 不会再动已归属单）。"""
    if rc_no:
        exist = db.execute(text(
            "SELECT id FROM pmwb_complaint_rootcause WHERE rootcause_no = :no"
        ), {"no": rc_no}).first()
        if not exist:
            return {"ok": False, "message": "根因簇不存在"}
    db.execute(text(
        "UPDATE pmwb_complaint_ticket SET rootcause_no = :rc, rc_status = "
        "CASE WHEN rc_status = 'manual' THEN rc_status ELSE rc_status END "
        "WHERE ticket_no = :no"
    ), {"rc": rc_no, "no": ticket_no})
    db.commit()
    refresh_counts(db)
    return {"ok": True}


def list_clusters(db: Session, status: str = "", keyword: str = "",
                  page: int = 1, page_size: int = 50) -> Dict[str, Any]:
    where = ["1 = 1"]
    params: Dict[str, Any] = {}
    if status:
        where.append("status = :st")
        params["st"] = status
    if keyword:
        where.append("(title LIKE :kw OR description LIKE :kw OR rootcause_no LIKE :kw)")
        params["kw"] = f"%{keyword}%"
    w = " AND ".join(where)
    total = db.execute(text(
        f"SELECT COUNT(*) FROM pmwb_complaint_rootcause WHERE {w}"), params).scalar() or 0
    params.update({"lim": int(page_size), "off": max(0, (int(page) - 1)) * int(page_size)})
    rows = db.execute(text(
        "SELECT rootcause_no, title, description, fault_stage, fault_system, fault_type, "
        "own_party, fix_mode, status, source, ticket_cnt, sample_tickets, first_week, "
        "last_week, merged_to, updated_at "
        f"FROM pmwb_complaint_rootcause WHERE {w} "
        "ORDER BY FIELD(status,'candidate','open','disabled','merged'), ticket_cnt DESC, id ASC "
        "LIMIT :lim OFFSET :off"
    ), params).fetchall()
    return {
        "total": int(total), "page": int(page), "page_size": int(page_size),
        "items": [{
            "rootcause_no": r[0], "title": r[1], "description": r[2] or "",
            "fault_stage": r[3] or "", "fault_system": r[4] or "",
            "fault_type": r[5] or "", "own_party": r[6] or "", "fix_mode": r[7] or "",
            "status": r[8], "status_label": RC.RC_LIB_STATUS_LABELS.get(r[8], r[8]),
            "source": r[9] or "", "ticket_cnt": int(r[10] or 0),
            "sample_tickets": json.loads(r[11] or "[]"),
            "first_week": r[12] or "", "last_week": r[13] or "",
            "merged_to": r[14] or "",
            "updated_at": r[15].strftime("%Y-%m-%d %H:%M") if r[15] else "",
        } for r in rows],
    }


def top_clusters(db: Session, week: str = "", limit: int = 20) -> List[Dict[str, Any]]:
    """分析口径：按簇单量排名（可限定周）。

    这是「哪些问题能一次消灭」的主数据源——簇单量 = 该根因的理论压降空间。
    """
    if week:
        rows = db.execute(text(
            "SELECT t.rootcause_no, r.title, r.fault_system, r.fault_stage, r.fault_type, "
            "r.own_party, r.fix_mode, r.status, COUNT(*) c "
            "FROM pmwb_complaint_ticket t JOIN pmwb_complaint_rootcause r "
            "  ON r.rootcause_no = t.rootcause_no "
            "WHERE t.week = :wk GROUP BY t.rootcause_no, r.title, r.fault_system, "
            "  r.fault_stage, r.fault_type, r.own_party, r.fix_mode, r.status "
            "ORDER BY c DESC LIMIT :n"
        ), {"wk": week, "n": int(limit)}).fetchall()
    else:
        rows = db.execute(text(
            "SELECT rootcause_no, title, fault_system, fault_stage, fault_type, own_party, "
            "fix_mode, status, ticket_cnt FROM pmwb_complaint_rootcause "
            "WHERE ticket_cnt > 0 ORDER BY ticket_cnt DESC LIMIT :n"
        ), {"n": int(limit)}).fetchall()
    return [{"rootcause_no": r[0], "title": r[1], "fault_system": r[2] or "",
             "fault_stage": r[3] or "", "fault_type": r[4] or "",
             "own_party": r[5] or "", "fix_mode": r[6] or "", "status": r[7],
             "cnt": int(r[8] or 0)} for r in rows]


def batch_clusters(db: Session, week: str = "", min_cnt: int = 3,
                   limit: int = 20) -> List[Dict[str, Any]]:
    """批量投诉识别（根因口径）：同一根因簇当周 >= min_cnt 单 → 判为批量问题。

    取代原「同一二级场景 + 同一自然日 >= 5 单」——按根因判定，抓的是
    「一处缺陷引发的一批投诉」，直接对应一次修复动作。
    """
    if not week:
        row = db.execute(text(
            "SELECT week FROM pmwb_complaint_ticket WHERE week IS NOT NULL AND week != '' "
            "ORDER BY week DESC LIMIT 1")).scalar()
        week = row or ""
    if not week:
        return []
    rows = db.execute(text(
        "SELECT t.rootcause_no, r.title, r.fault_system, r.fault_stage, r.fault_type, "
        "r.own_party, r.fix_mode, r.status, COUNT(*) c, "
        "COUNT(DISTINCT DATE(t.created_time)) d "
        "FROM pmwb_complaint_ticket t JOIN pmwb_complaint_rootcause r "
        "  ON r.rootcause_no = t.rootcause_no "
        "WHERE t.week = :wk GROUP BY t.rootcause_no, r.title, r.fault_system, "
        "  r.fault_stage, r.fault_type, r.own_party, r.fix_mode, r.status "
        "HAVING c >= :mc ORDER BY c DESC LIMIT :n"
    ), {"wk": week, "mc": int(min_cnt), "n": int(limit)}).fetchall()
    return [{"rootcause_no": r[0], "title": r[1], "fault_system": r[2] or "",
             "fault_stage": r[3] or "", "fault_type": r[4] or "",
             "own_party": r[5] or "", "fix_mode": r[6] or "", "status": r[7],
             "cnt": int(r[8] or 0), "days": int(r[9] or 0), "week": week}
            for r in rows]


def rootcause_detail(db: Session, rc_no: str) -> Optional[Dict[str, Any]]:
    """簇详情 + 关联工单（分析下钻用）。"""
    r = db.execute(text(
        "SELECT rootcause_no, title, description, fault_stage, fault_system, fault_type, "
        "own_party, fix_mode, status, ticket_cnt, sample_tickets, first_week, last_week "
        "FROM pmwb_complaint_rootcause WHERE rootcause_no = :no"
    ), {"no": rc_no}).first()
    if not r:
        return None
    tickets = db.execute(text(
        "SELECT ticket_no, week, city, LEFT(root_cause, 200), rc_status, rc_confidence "
        "FROM pmwb_complaint_ticket WHERE rootcause_no = :no ORDER BY id DESC LIMIT 50"
    ), {"no": rc_no}).fetchall()
    return {
        "rootcause_no": r[0], "title": r[1], "description": r[2] or "",
        "fault_stage": r[3] or "", "fault_system": r[4] or "", "fault_type": r[5] or "",
        "own_party": r[6] or "", "fix_mode": r[7] or "", "status": r[8],
        "status_label": RC.RC_LIB_STATUS_LABELS.get(r[8], r[8]),
        "ticket_cnt": int(r[9] or 0), "sample_tickets": json.loads(r[10] or "[]"),
        "first_week": r[11] or "", "last_week": r[12] or "",
        "tickets": [{"ticket_no": t[0], "week": t[1] or "", "city": t[2] or "",
                     "root_cause": t[3] or "", "rc_status": t[4] or "",
                     "rc_confidence": float(t[5] or 0)} for t in tickets],
    }
