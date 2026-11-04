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

RC-2.0 改造（2026-11-04，老大拍板「不涉及用户级信息、簇数 ≤100」）：
  - **簇键 = (环节, 机制, 上位对象) 三元组**，唯一实现 `constants.complaint_pattern.pattern_key`；
    原来只按 (系统, 环节) 分桶，而系统是「断点归因」不是「问题身份」——实测同一问题
    被拆到 CRM/电视平台/订单中心 3 个桶合计 28 单，故系统降级为属性、不进键。
  - 分桶由 `(fault_system, fault_stage)` 改为 `(fault_stage, rc_mechanism)`；
  - 三个新动作：
      `relabel_clusters`     历史簇一次性结构化标定（簇级 22 批，比重跑 1476 单便宜 7 倍）
      `consolidate_by_pattern` 按三元组合并簇（纯规则、0 LLM、可回滚）
      `cluster_health` / `closing_check`  质量指标与闭合校验

写入边界：pmwb_complaint_ticket.rootcause_no 的**唯一写入点**是本模块 build_clusters/merge。
         root_pattern / rc_mechanism / rc_object 的写入点：rootcause.py（新单 L1）
         与 relabel_clusters（历史回填），两者口径同源 constants/complaint_pattern。
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

from constants import complaint_pattern as P
from constants import complaint_rootcause as RC
from services.complaint import config as C
from services.complaint.llm_classify import _extract_json
from services.llm_provider import call_best_available

logger = logging.getLogger(__name__)

CLUSTER_BATCH = 20          # 每批送 LLM 归并的根因条数
RELABEL_BATCH = 10          # 每批做模式标定的簇数（实测 20/40 都会漏返，10 最稳；漏的下轮 only_missing 补）
CONSULT_RATIO_MAX = 0.5     # 单批内「无咨询特征却标使用咨询」占比上限，超了判该批退化、整批拒收
# 咨询/非缺陷的文本特征（与 LLM 判定做双向校验：模型说是咨询，原文也得像咨询）
CONSULT_HINTS: Tuple[str, ...] = (
    "非缺陷", "非系统缺陷", "无缺陷", "解释", "咨询", "理解偏差", "认知",
    "操作问题", "操作不当", "正常", "规则说明", "查询确认", "待查证", "符合规则",
)


def _looks_consult(title: str, desc: str = "") -> bool:
    s = f"{title or ''}{desc or ''}"
    return any(h in s for h in CONSULT_HINTS)
LIB_IN_PROMPT_MAX = 60      # prompt 中展示的库内簇上限（控 token）

# 桶内归并（主动分组）—— 2026-11-03 重构说明：
#   原先「逐条判定归入哪个已有簇 / 或 NEW」在实测中退化成 1 单 1 簇（228 单 → 140 簇）：
#   每条根因都带不同的单号账号，模型逐条看就都觉得「机制不同」，且天然倾向 NEW。
#   改为「先分桶，再让模型在桶内主动分组」——一次看到全桶样本，分组是全局视角。
# 2026-11-04 RC-2.0：桶键由 (系统+环节) 改为 (环节+机制)，桶内只按**业务对象**分组。
#   机制已被上游锁定，模型不再需要判断「怎么断的」，只需判断「断在谁身上」，任务更窄更稳。
_CLUSTER_PROMPT = (
    "你是电信运营商政企/商客业务客诉根因归并专家。下面给出同一个「订单环节 + 失败机制」"
    "桶内的若干条工单根因，请按**业务对象**把它们分成尽可能少的组（通常 1~3 组）。\n"
    "分组标准（重要）：同一组内的对象必须是同一个业务实体（订单 / 施工单 / 产品实例 / "
    "宽带账号 / 账单 …）；仅仅因为单号、账号、客户名、日期不同而措辞有差异的，属于**同一组**，不得拆开。\n"
    "业务对象只能从给定枚举里选，不得自由造词。\n"
    "若同对象但**修复点明显不同**，填 trigger（≤12 字）区分，例如「集团编码超长」与「营销案未配置」"
    "同为「校验拦截 + 客户资料/营销案」但一个改字段长度、一个补配置，必须分开。\n"
    "必须覆盖给出的全部工单号，不能漏。\n"
    "输出仅 JSON："
    '{"clusters": [{"biz_object": "...", "trigger": "", '
    '"description": "判定边界一句话", "members": ["工单号", "..."]}]}'
)


def _short_title_from_pattern(t: Dict[str, Any]) -> str:
    """无模式可用的极端兜底标题（不含用户级信息，绝不截 L1 原文）。"""
    obj = (t.get("rc_object") or "").strip() or P.OBJECT_FALLBACK
    mech = (t.get("rc_mechanism") or "").strip() or P.MECHANISM_FALLBACK
    return f"{obj}-{mech}"

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
        "SELECT ticket_no, root_cause, fault_system, fault_stage, fault_type, rc_status, week, "
        "rc_mechanism, rc_object, rc_trigger, root_pattern "
        "FROM pmwb_complaint_ticket "
        "WHERE root_cause IS NOT NULL AND root_cause != '' "
        "AND (rootcause_no IS NULL OR rootcause_no = '') "
        f"ORDER BY rc_status DESC, fault_system ASC, fault_stage ASC, id ASC{lim}"
    )).fetchall()
    return [{"ticket_no": r[0], "root_cause": r[1], "fault_system": r[2],
             "fault_stage": r[3], "fault_type": r[4], "rc_status": r[5], "week": r[6],
             "rc_mechanism": r[7] or "", "rc_object": r[8] or "",
             "rc_trigger": r[9] or "", "root_pattern": r[10] or ""}
            for r in rows]


def find_by_key(db: Session, key: str) -> Optional[str]:
    """按三元组键查存活簇（open 优先于 candidate）——入库前必匹配的第一道闸。"""
    if not key:
        return None
    row = db.execute(text(
        "SELECT rootcause_no FROM pmwb_complaint_rootcause "
        "WHERE pattern_key = :k AND status IN ('open','candidate') "
        "ORDER BY CASE status WHEN 'open' THEN 0 ELSE 1 END, ticket_cnt DESC, id ASC LIMIT 1"
    ), {"k": key}).scalar()
    return row


def count_bucket_clusters(db: Session, stage: str, mechanism: str,
                          exclude: str = "") -> int:
    """某（环节 × 机制）下现存存活簇数（配额熔断用）。"""
    row = db.execute(text(
        "SELECT COUNT(*) FROM pmwb_complaint_rootcause "
        "WHERE fault_stage = :st AND mechanism = :mc AND status IN ('open','candidate') "
        "AND (:ex = '' OR rootcause_no != :ex)"
    ), {"st": stage, "mc": mechanism, "ex": exclude or ""}).scalar()
    return int(row or 0)


def _create_cluster(db: Session, title: str, description: str,
                    tickets: List[Dict[str, Any]], key: Optional[tuple] = None,
                    stage: str = "", mechanism: str = "", biz_object: str = "") -> str:
    """新建候选簇。**先按三元组键复用**（未命中再按标题），保证增量不重复造簇。"""
    pkey = P.pattern_key(stage, mechanism, biz_object) if (stage and mechanism) else ""
    if pkey:
        exist = find_by_key(db, pkey)
        if exist:
            return exist
    title = title.strip()[:200]
    if not title:
        return ""
    exist = db.execute(text(
        "SELECT rootcause_no FROM pmwb_complaint_rootcause WHERE title = :t "
        "AND status IN ('open','candidate') LIMIT 1"
    ), {"t": title}).scalar()
    if exist:
        return exist
    no = _next_rc_no(db)
    first = tickets[0] if tickets else {}
    sys_cnt = Counter(t.get("fault_system") or "" for t in tickets).most_common(1)
    stage_cnt = Counter(t.get("fault_stage") or "" for t in tickets).most_common(1)
    ftype = Counter(t.get("fault_type") or "" for t in tickets).most_common(1)
    mech_cnt = Counter(t.get("rc_mechanism") or "" for t in tickets).most_common(1)
    obj_cnt = Counter(t.get("rc_object") or "" for t in tickets).most_common(1)
    is_defect = 0 if (mechanism or (mech_cnt[0][0] if mech_cnt else "")) == P.MECHANISM_CONSULT else 1
    db.execute(text(
        "INSERT INTO pmwb_complaint_rootcause "
        "(rootcause_no, title, description, fault_system, fault_stage, fault_type, "
        " mechanism, biz_object, pattern_key, is_defect, "
        " status, source, ticket_cnt, sample_tickets, first_week, last_week, "
        " created_at, updated_at) "
        "VALUES (:no, :title, :desc, :sys, :stage, :ftype, :mc, :ob, :pk, :df, "
        " 'candidate', 'ai', 0, :samples, :wk, :wk, :ts, :ts)"
    ), {"no": no, "title": title, "desc": (description or "").strip()[:500],
        "sys": sys_cnt[0][0] if sys_cnt else "",
        "stage": stage or (stage_cnt[0][0] if stage_cnt else ""),
        "ftype": ftype[0][0] if ftype else "",
        "mc": mechanism or (mech_cnt[0][0] if mech_cnt else "") or None,
        "ob": biz_object or (obj_cnt[0][0] if obj_cnt else "") or None,
        "pk": pkey or None, "df": is_defect,
        "samples": json.dumps([t["ticket_no"] for t in tickets[:8]], ensure_ascii=False),
        "wk": first.get("week") or "", "ts": datetime.now()})
    return no


def _point(db: Session, ticket_no: str, rc_no: str) -> None:
    db.execute(text(
        "UPDATE pmwb_complaint_ticket SET rootcause_no = :rc WHERE ticket_no = :no"
    ), {"rc": rc_no, "no": ticket_no})


def _existing_titles(db: Session, key: tuple) -> List[str]:
    """该 (环节×机制) 桶已有的簇（对象 + 模式），供桶内分组复用，保证增量不重复造簇。"""
    stage, mech = key
    try:
        rows = db.execute(text(
            "SELECT title, biz_object, pattern_key FROM pmwb_complaint_rootcause "
            "WHERE status IN ('open','candidate') AND fault_stage = :st AND mechanism = :mc "
            "ORDER BY ticket_cnt DESC LIMIT 20"
        ), {"st": stage, "mc": mech}).fetchall()
    except Exception:  # noqa: BLE001
        return []
    return [f"{(r[1] or '?')}｜{r[0]}" for r in rows]


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
            # 三元组键不同不得合并：否则 ticket.pattern_key 与簇键失配，
            # 后续按键匹配会全部打空（RC-2.0 口径保护）
            pair = db.execute(text(
                "SELECT (SELECT pattern_key FROM pmwb_complaint_rootcause WHERE rootcause_no = :a), "
                "       (SELECT pattern_key FROM pmwb_complaint_rootcause WHERE rootcause_no = :b)"
            ), {"a": src, "b": keep}).first()
            if pair and pair[0] and pair[1] and pair[0] != pair[1]:
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
    stage, mech = key
    parts = [f"【桶】订单环节={stage}｜失败机制={mech}｜共 {len(tickets)} 单"]
    if existing:
        parts.append("【该桶已有根因簇（对象相同的请直接沿用其对象名，不要另造）】")
        parts.extend(f"- {t}" for t in existing)
    parts.append(f"\n【业务对象枚举（只能从中选）】{'、'.join(P.OBJECTS)}")
    parts.append("\n【根因列表】（机制与环节已定，只需判断业务对象）")
    for t in tickets:
        parts.append(f'工单 {t["ticket_no"]}：{t.get("root_cause") or ""}')
    parts.append("\n请按业务对象分组并输出 JSON（clusters 数组，必须覆盖全部工单号）。")
    return "\n".join(parts)


def _group_bucket(db: Session, key: tuple, tickets: List[Dict[str, Any]]
                  ) -> Tuple[List[Dict[str, Any]], int]:
    """桶内主动分组：返回 ([{obj, trigger, desc, members}], LLM 失败单数)。

    单条 chunk 不再「从原文截标题」——直接用 L1 已定的对象，标题=受控模式，
    因此不会再退化成 1 单 1 簇（历史上 `_short_title` 单条成簇是碎片产线）。
    """
    existing = _existing_titles(db, key)
    groups: List[Dict[str, Any]] = []
    failed = 0
    for i in range(0, len(tickets), CLUSTER_BATCH):
        chunk = tickets[i:i + CLUSTER_BATCH]
        if len(chunk) == 1:
            t = chunk[0]
            groups.append({"obj": t.get("rc_object") or P.OBJECT_FALLBACK,
                           "trigger": t.get("rc_trigger") or "",
                           "desc": "", "members": [t]})
            continue
        res = call_best_available(db, _CLUSTER_PROMPT,
                                  _bucket_prompt(key, chunk, existing),
                                  max_tokens=4000, timeout=300)
        if not res.get("used_llm"):
            failed += len(chunk)
            for t in chunk:
                groups.append({"obj": t.get("rc_object") or P.OBJECT_FALLBACK,
                               "trigger": t.get("rc_trigger") or "",
                               "desc": "", "members": [t]})
            continue
        data = _extract_json(res.get("text") or "") or {}
        by_no = {t["ticket_no"]: t for t in chunk}
        covered: set = set()
        for c in (data.get("clusters") or []):
            if not isinstance(c, dict):
                continue
            obj = P.normalize_object(str(c.get("biz_object") or ""))
            members = [str(m).strip() for m in (c.get("members") or [])]
            ts = [by_no[m] for m in members if m in by_no and m not in covered]
            if not ts:
                continue
            covered.update(members)
            groups.append({
                "obj": obj or (ts[0].get("rc_object") or P.OBJECT_FALLBACK),
                "trigger": str(c.get("trigger") or "").strip()[:64],
                "desc": str(c.get("description") or "").strip()[:500],
                "members": ts})
        for t in chunk:
            if t["ticket_no"] not in covered:
                groups.append({"obj": t.get("rc_object") or P.OBJECT_FALLBACK,
                               "trigger": t.get("rc_trigger") or "",
                               "desc": "", "members": [t]})
    return groups, failed


def _ensure_cluster(db: Session, stage: str, mech: str, obj: str, trigger: str,
                    desc: str, members: List[Dict[str, Any]]) -> Tuple[str, str]:
    """入库前必匹配 → 配额熔断 → 才允许新建。返回 (簇号, 命中方式)。

    四道闸里的第 2、3 道：先按 (环节,机制,上位对象) 精确匹配；未命中且该桶簇数
    已达 BUCKET_CLUSTER_MAX 时，强制归入该桶「其他」兜底簇（记 quota，等月度重构）。
    """
    obj = P.normalize_object(obj) or P.OBJECT_FALLBACK
    rc_no = find_by_key(db, P.pattern_key(stage, mech, obj))
    if rc_no:
        return rc_no, "matched"
    if mech != P.MECHANISM_FALLBACK and \
            count_bucket_clusters(db, stage, mech) >= P.BUCKET_CLUSTER_MAX:
        obj, how = P.OBJECT_FALLBACK, "quota"
        rc_no = find_by_key(db, P.pattern_key(stage, mech, obj))
        if rc_no:
            return rc_no, how
    title = P.build_pattern(mech, obj, trigger)
    if P.pattern_violations(title):      # trigger 违规就去掉 trigger，模式本身仍合法
        title = P.build_pattern(mech, obj)
    rc_no = _create_cluster(db, title, desc, members,
                            stage=stage, mechanism=mech, biz_object=obj)
    return rc_no, "new"


_LABEL_PROMPT = (
    "你是客诉根因标定专家。请把每条根因抽象成**可复用模式三要素**，"
    "**严禁带入账号、订单号、协议号、客户名、地市门牌、日期、金额**。\n"
    " · fault_stage 订单环节（按**断点所在环节**判定，不按客户投诉提到的环节）\n"
    " · mechanism 失败机制（怎么断的）\n"
    " · biz_object 业务对象（断在谁身上）\n"
    " · trigger ≤12 字，可空；仅当同对象同机制但修复点明显不同时才填\n"
    "三个要素都必须从给定枚举里选，不得自由造词。\n"
    "输出仅 JSON："
    '{"items": [{"no": "...", "fault_stage": "...", "mechanism": "...", '
    '"biz_object": "...", "trigger": ""}]}'
)


def _label_user_prompt(rows: List[str]) -> str:
    return (P.enum_block() + "\n【机制判定参考】\n" + P.mechanism_rules_block()
            + "\n\n【待标定条目】\n" + "\n".join(rows)
            + f"\n\n请逐条输出三要素（共 {len(rows)} 条），仅输出 JSON。")


def label_ticket_patterns(db: Session, tickets: List[Dict[str, Any]]) -> int:
    """给缺模式的工单补三要素并回填（L1 已输出的不会重复调用）。

    历史数据回填的**唯一入口之一**（另一个是 relabel_clusters，簇级更便宜）。
    """
    todo = [t for t in tickets
            if (t.get("rc_mechanism") or "") not in P.MECHANISMS
            or (t.get("rc_object") or "") not in P.OBJECTS]
    if not todo:
        return 0
    filled = 0
    for i in range(0, len(todo), C.RC_BATCH_SIZE):
        chunk = todo[i:i + C.RC_BATCH_SIZE]
        rows = [f'工单 {t["ticket_no"]}：{(t.get("root_cause") or "")[:200]}' for t in chunk]
        res = call_best_available(db, _LABEL_PROMPT, _label_user_prompt(rows),
                                  max_tokens=4000, timeout=300)
        if not res.get("used_llm"):
            break
        data = _extract_json(res.get("text") or "") or {}
        by_no = {t["ticket_no"]: t for t in chunk}
        for it in (data.get("items") or []):
            if not isinstance(it, dict):
                continue
            no = str(it.get("no") or "").strip()
            t = by_no.get(no)
            if not t:
                continue
            stage = RC.normalize_choice(str(it.get("fault_stage") or ""), RC.FAULT_STAGES)
            mech = P.normalize_mechanism(str(it.get("mechanism") or ""))
            obj = P.normalize_object(str(it.get("biz_object") or ""))
            trig = str(it.get("trigger") or "").strip()[:64]
            pattern = P.build_pattern(mech, obj, trig)
            if not mech or not obj or P.pattern_violations(pattern):
                pattern = P.build_pattern(mech, obj)
            db.execute(text(
                "UPDATE pmwb_complaint_ticket SET rc_mechanism = :mc, rc_object = :ob, "
                "rc_trigger = :tg, root_pattern = :pt, "
                "fault_stage = COALESCE(NULLIF(:st, ''), fault_stage) "
                "WHERE ticket_no = :no"
            ), {"mc": mech or None, "ob": obj or None, "tg": trig or None,
                "pt": pattern or None, "st": stage or "", "no": no})
            if mech and obj:
                filled += 1
            # 内存同步，避免后续分桶还按旧值
            t["rc_mechanism"], t["rc_object"] = mech, obj
            t["rc_trigger"], t["root_pattern"] = trig, pattern
            if stage:
                t["fault_stage"] = stage
        db.commit()
    return filled


def build_clusters(db: Session, limit: Optional[int] = None) -> Dict[str, Any]:
    """把未归属的 L1 根因归并进根因库（新簇先落 candidate，人工确认后 open）。

    三步走（RC-2.0，2026-11-04）：
      ① 补标：缺模式三要素的单先补（新单由 L1 直接产出，只有历史/异常单会走这里）；
      ② 规则分桶：按 **环节 + 失败机制** 分桶（机制是收敛轴，系统降级为属性不进桶）；
      ③ 桶内分组：LLM 一次看全桶样本，只判断「断在哪个业务对象上」；
         然后按三元组键精确匹配库内簇，未命中才在配额内新建。
    这样既消除「同机制跨系统被拆 4 簇」，也不会退化成 1 单 1 簇。
    """
    pending = _tickets_to_group(db, limit)
    if not pending:
        return {"scanned": 0, "assigned": 0, "new_clusters": [], "failed": 0,
                "used_llm": False, "notice": "没有待归并的根因"}

    relabeled = label_ticket_patterns(db, pending)

    consult: List[Dict[str, Any]] = []
    buckets: Dict[tuple, List[Dict[str, Any]]] = {}
    skipped = 0
    for t in pending:
        stage = (t.get("fault_stage") or "").strip()
        mech = (t.get("rc_mechanism") or "").strip()
        if mech not in P.MECHANISMS or not stage:
            skipped += 1          # 模式补不出来：不造簇，等下一轮（宁缺不碎）
            continue
        if mech == P.MECHANISM_CONSULT:
            consult.append(t)
            continue
        buckets.setdefault((stage, mech), []).append(t)

    assigned = failed = quota_hits = 0
    new_clusters: List[str] = []
    used_llm = False

    # 咨询单：单列一簇，不参与缺陷簇统计（is_defect=0）
    if consult:
        rc_no, how = _ensure_cluster(db, P.MECHANISM_CONSULT, P.MECHANISM_CONSULT,
                                     P.OBJECT_FALLBACK, "",
                                     "操作不熟或认知偏差，系统与流程均正常（非缺陷）",
                                     consult)
        for t in consult:
            _point(db, t["ticket_no"], rc_no)
            assigned += 1
        if rc_no and rc_no not in new_clusters:
            new_clusters.append(rc_no)
        db.commit()

    # 大桶先处理（主题优先）
    for key in sorted(buckets.keys(), key=lambda k: -len(buckets[k])):
        ts = buckets[key]
        groups, bad = _group_bucket(db, key, ts)
        failed += bad
        used_llm = used_llm or (bad < len(ts))
        for g in groups:
            rc_no, how = _ensure_cluster(db, key[0], key[1], g["obj"], g["trigger"],
                                         g["desc"], g["members"])
            if how == "quota":
                quota_hits += len(g["members"])
            if not rc_no:
                failed += len(g["members"])
                continue
            for t in g["members"]:
                _point(db, t["ticket_no"], rc_no)
                assigned += 1
            if rc_no not in new_clusters:
                new_clusters.append(rc_no)
        db.commit()

    refresh_counts(db, update_labels=True)
    return {
        "scanned": len(pending), "assigned": assigned, "failed": failed,
        "new_clusters": new_clusters, "buckets": len(buckets),
        "relabeled": relabeled, "skipped": skipped, "quota_fallback": quota_hits,
        "used_llm": used_llm,
        "notice": ("根因归并完成" if used_llm else "大模型不可用，未做归并"),
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
        "  GROUP_CONCAT(own_party), GROUP_CONCAT(fix_mode), "
        "  GROUP_CONCAT(rc_mechanism), GROUP_CONCAT(rc_object) "
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

    for rc_no, cnt, fw, lw, stages, ftypes, parties, fixes, mechs, objs in rows:
        sets = ["ticket_cnt = :c", "first_week = :fw", "last_week = :lw",
                "sample_tickets = :s", "updated_at = :ts"]
        params: Dict[str, Any] = {
            "c": int(cnt), "fw": fw or "", "lw": lw or "",
            "s": json.dumps(samples_map.get(rc_no) or [], ensure_ascii=False),
            "no": rc_no, "ts": datetime.now()}
        if update_labels:
            stage_v, mech_v, obj_v = _mode(stages), _mode(mechs), _mode(objs)
            sets += ["fault_stage = :stage", "fault_type = :ftype",
                     "own_party = :party", "fix_mode = :fix",
                     "mechanism = :mech", "biz_object = :obj"]
            params.update({"stage": stage_v, "ftype": _mode(ftypes),
                           "party": _mode(parties), "fix": _mode(fixes),
                           "mech": mech_v or None, "obj": obj_v or None})
            # 三元组键：环节/机制/上位对象都在时才写（缺一不猜）
            if stage_v and mech_v and obj_v:
                sets.append("pattern_key = :pk")
                params["pk"] = P.pattern_key(stage_v, mech_v, obj_v)
        db.execute(text(
            f"UPDATE pmwb_complaint_rootcause SET {', '.join(sets)} WHERE rootcause_no = :no"
        ), params)
    if commit:
        db.commit()
    return {"clusters": len(rows)}


# ── RC-2.0 簇重建（历史数据一次性收敛）────────────────────────
_CLUSTER_LABEL_PROMPT = (
    "你是客诉根因库的标定专家。下面每个簇已经是一个「同类根因」，请为每个簇标定三要素，"
    "用于跨簇归并（同一「环节 + 机制 + 业务对象」应当收敛成一个簇）。\n"
    " · fault_stage 订单环节，按**断点所在环节**判定，不按客户投诉提到的环节\n"
    " · mechanism 失败机制（怎么断的）\n"
    " · biz_object 业务对象（断在谁身上）\n"
    " · trigger ≤12 字，可空；仅当同对象同机制但修复点明显不同时才填\n"
    "判定只看断点在哪、怎么断的、断在谁身上，**不要被具体单号账号干扰**。\n"
    "三个要素必须从给定枚举中选，不得自由造词；咨询/非缺陷簇的 mechanism 填「使用咨询」。\n"
    "输出仅 JSON："
    '{"items": [{"no": "RC-0001", "fault_stage": "...", "mechanism": "...", '
    '"biz_object": "...", "trigger": ""}]}'
)


def relabel_clusters(db: Session, limit: Optional[int] = None,
                     only_missing: bool = False, retitle: bool = True,
                     dry_run: bool = False) -> Dict[str, Any]:
    """给存量簇做模式标定（环节 / 机制 / 对象 / 触发条件），并回填成员工单。

    为什么走「簇级」而不是重跑 1476 单 L1：858 簇 ÷ 40 ≈ 22 批，
    比重跑工单（≈150 批）便宜 7 倍；且模型一次看 40 个簇是全局视角，天然收敛。
    这是历史 `root_pattern` 回填的**唯一入口**（另一个是 L1 对新单的直接产出）。

    dry_run=True 只返回标定结果不动库（含每簇 before/after），用于先看质量。
    """
    cond = "status IN ('open','candidate')"
    if only_missing:
        cond += " AND (mechanism IS NULL OR mechanism = '')"
    lim = f" LIMIT {int(limit)}" if limit else ""
    rows = db.execute(text(
        "SELECT rootcause_no, title, description, fault_stage, fault_system, ticket_cnt, "
        f"sample_tickets, status, source, is_defect FROM pmwb_complaint_rootcause WHERE {cond}{lim}"
    )).fetchall()
    if not rows:
        return {"scanned": 0, "labeled": 0, "failed": 0, "changed_stage": 0,
                "notice": "没有需要标定的簇"}

    # 代表单根因摘要（跨库安全：sample_tickets 是 JSON，Python 侧解析）
    samples: Dict[str, List[str]] = {}
    for rc_no, raw in db.execute(text(
        "SELECT rootcause_no, sample_tickets FROM pmwb_complaint_rootcause "
        f"WHERE {cond}{lim}"
    )).fetchall():
        try:
            samples[rc_no] = json.loads(raw or "[]")[:2]
        except (TypeError, ValueError):
            samples[rc_no] = []
    ex_rows = db.execute(text(
        "SELECT ticket_no, rootcause_no, LEFT(root_cause, 120) FROM pmwb_complaint_ticket "
        "WHERE rootcause_no IS NOT NULL AND rootcause_no != '' ORDER BY id ASC"
    )).fetchall()
    ex_map: Dict[str, List[str]] = {}
    for tno, rc_no, cause in ex_rows:
        lst = ex_map.setdefault(rc_no, [])
        if len(lst) < 2 and cause:
            lst.append(cause)

    labeled = failed = changed_stage = 0
    used_llm = False
    preview: List[Dict[str, Any]] = []
    for i in range(0, len(rows), RELABEL_BATCH):
        chunk = rows[i:i + RELABEL_BATCH]
        # 漏返重试：实测模型偶发只返回前几条（20 条只回 4 条），对剩余条目补调一次
        todo_rows = list(chunk)
        for attempt in range(3):
            if not todo_rows:
                break
            lines = []
            for r in todo_rows:
                ex = "；".join(ex_map.get(r[0]) or [])
                lines.append(f"{r[0]}｜{r[5]} 单｜原环节={r[3] or '?'}｜{r[1]}"
                             + (f"｜例：{ex}" if ex else ""))
            res = call_best_available(db, _CLUSTER_LABEL_PROMPT, _label_user_prompt(lines),
                                      max_tokens=8000, timeout=300)
            if not res.get("used_llm"):
                break
            used_llm = True
            data = _extract_json(res.get("text") or "") or {}
            raw_items = [it for it in (data.get("items") or []) if isinstance(it, dict)]
            if not raw_items:
                continue
            # 批次退化防护：模型「偷懒」时会整批填「使用咨询」（实测 40 条一批时出现）。
            # 只统计「原文毫无咨询特征却标咨询」的数量——真咨询簇允许被标为咨询。
            by_no = {r[0]: r for r in todo_rows}
            consult_hits = 0
            for it in raw_items:
                r = by_no.get(str(it.get("no") or "").strip())
                if not r:
                    continue
                if P.normalize_mechanism(str(it.get("mechanism") or "")) != P.MECHANISM_CONSULT:
                    continue
                if (r[3] or "") == P.MECHANISM_CONSULT or int(r[9] or 1) == 0:
                    continue
                if not _looks_consult(r[1], r[2]):
                    consult_hits += 1
            if len(raw_items) >= 5 and consult_hits / len(raw_items) > CONSULT_RATIO_MAX:
                logger.warning("簇标定批次退化（无据标咨询 %d/%d），整批拒收",
                               consult_hits, len(raw_items))
                failed += len(todo_rows)
                break
            handled = set()
            for it in raw_items:
                no = str(it.get("no") or "").strip()
                r = by_no.get(no)
                if not r or no in handled:
                    continue
                stage = RC.normalize_choice(str(it.get("fault_stage") or ""), RC.FAULT_STAGES)
                mech = P.normalize_mechanism(str(it.get("mechanism") or ""))
                obj = P.normalize_object(str(it.get("biz_object") or ""))
                trig = str(it.get("trigger") or "").strip()[:64]
                if not mech or not obj:
                    # 落不到枚举（模型可能填了分组名）：不标记 handled，下一轮重试
                    continue
                # 「使用咨询」门禁：模型判咨询，原文必须有咨询特征（防偷懒降级）。
                # 判据双向对齐后，is_defect 也统一按机制派生（不再按 fault_stage 猜）。
                if mech == P.MECHANISM_CONSULT and \
                        (r[3] or "") != P.MECHANISM_CONSULT and int(r[9] or 1) == 1 \
                        and not _looks_consult(r[1], r[2]):
                    continue
                handled.add(no)
                pattern = P.build_pattern(mech, obj, trig)
                if P.pattern_violations(pattern):
                    pattern = P.build_pattern(mech, obj)
                labeled += 1
                if stage and stage != (r[3] or ""):
                    changed_stage += 1
                if dry_run:
                    preview.append({"no": no, "old_title": r[1], "old_stage": r[3] or "",
                                    "stage": stage or r[3] or "", "mechanism": mech,
                                    "biz_object": obj, "trigger": trig,
                                    "pattern": pattern, "cnt": int(r[5] or 0)})
                    continue
                sets = ["mechanism = :mc", "biz_object = :ob", "updated_at = :ts",
                        "is_defect = :df"]
                params: Dict[str, Any] = {"mc": mech, "ob": obj, "no": no,
                                          "df": 0 if mech == P.MECHANISM_CONSULT else 1,
                                          "ts": datetime.now()}
                eff_stage = stage or (r[3] or "")
                if eff_stage:
                    sets.append("fault_stage = :st")
                    params["st"] = eff_stage
                    sets.append("pattern_key = :pk")
                    params["pk"] = P.pattern_key(eff_stage, mech, obj)
                # 标题统一改为受控模式（人工命名过的不动）
                if retitle and (r[8] or "ai") != "manual":
                    sets.append("title = :ti")
                    params["ti"] = pattern
                db.execute(text(
                    f"UPDATE pmwb_complaint_rootcause SET {', '.join(sets)} "
                    "WHERE rootcause_no = :no"), params)
                # 回填成员工单的 pattern（只填空，绝不覆盖 L1 已产出的结果）
                db.execute(text(
                    "UPDATE pmwb_complaint_ticket SET rc_mechanism = :mc, rc_object = :ob, "
                    "root_pattern = :pt "
                    "WHERE rootcause_no = :no AND (root_pattern IS NULL OR root_pattern = '')"
                ), {"mc": mech, "ob": obj, "pt": pattern, "no": no})
            todo_rows = [r for r in todo_rows if r[0] not in handled]
        failed += len(todo_rows)      # 三轮仍落不到枚举的，计失败（下轮 only_missing 自愈）
        if not dry_run:
            db.commit()

    out: Dict[str, Any] = {"scanned": len(rows), "labeled": labeled, "failed": failed,
                           "changed_stage": changed_stage, "used_llm": used_llm,
                           "dry_run": dry_run,
                           "notice": "簇模式标定完成" if used_llm else "大模型不可用，未标定"}
    if dry_run:
        out["preview"] = preview
    return out


def consolidate_by_pattern(db: Session, dry_run: bool = True) -> Dict[str, Any]:
    """按三元组键把同键簇合并成一个（纯规则、0 LLM、走 merged_to 可回滚）。

    dry_run=True 只出报告不动库（含每组的保留/被并清单），便于先看影响面。
    """
    rows = db.execute(text(
        "SELECT rootcause_no, pattern_key, title, status, ticket_cnt, is_defect "
        "FROM pmwb_complaint_rootcause "
        "WHERE status IN ('open','candidate') AND pattern_key IS NOT NULL AND pattern_key != '' "
        "ORDER BY pattern_key, id ASC"
    )).fetchall()
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for rc_no, key, title, status, cnt, df in rows:
        groups.setdefault(key, []).append(
            {"no": rc_no, "title": title, "status": status,
             "cnt": int(cnt or 0), "is_defect": int(df or 1)})

    plan: List[Dict[str, Any]] = []
    for key, items in groups.items():
        if len(items) < 2:
            continue
        # 保留规则：open 优先 → 单量大 → 簇号小（可预测，便于复核）
        keep = sorted(items, key=lambda x: (0 if x["status"] == "open" else 1,
                                            -x["cnt"], x["no"]))[0]
        absorb = [x["no"] for x in items if x["no"] != keep["no"]]
        plan.append({"key": key, "keep": keep["no"], "absorb": absorb,
                     "single_hits": sum(1 for x in items if x["cnt"] <= 1)})

    before = len(rows)
    after = before - sum(len(p["absorb"]) for p in plan)
    out: Dict[str, Any] = {
        "dry_run": dry_run, "clusters_before": before, "clusters_after_est": after,
        "groups": len(plan), "absorb_count": sum(len(p["absorb"]) for p in plan),
        "plan": plan[:80],
    }
    if dry_run:
        return out

    merged = 0
    for p in plan:
        # 主簇标题统一为受控模式 `{对象}-{机制}`（人工命名过的不动）
        _st, _mc, _ob = p["key"].split(P.KEY_SEP)
        db.execute(text(
            "UPDATE pmwb_complaint_rootcause SET title = :t, updated_at = :ts "
            "WHERE rootcause_no = :no AND (source IS NULL OR source != 'manual')"
        ), {"t": P.build_pattern(_mc, _ob), "no": p["keep"], "ts": datetime.now()})
        # 批量迁移指针 + 置 merged（不逐簇调 merge()：那样每簇都全表重算，483 簇要走几十分钟）
        if p["absorb"]:
            marks = ",".join(f":a{i}" for i in range(len(p["absorb"])))
            aparams: Dict[str, Any] = {f"a{i}": v for i, v in enumerate(p["absorb"])}
            aparams.update({"keep": p["keep"], "ts": datetime.now()})
            db.execute(text(
                f"UPDATE pmwb_complaint_ticket SET rootcause_no = :keep "
                f"WHERE rootcause_no IN ({marks})"), aparams)
            db.execute(text(
                f"UPDATE pmwb_complaint_rootcause SET status = 'merged', merged_to = :keep, "
                f"ticket_cnt = 0, updated_at = :ts WHERE rootcause_no IN ({marks})"), aparams)
            merged += len(p["absorb"])
        db.commit()
    # 收尾统一做一次：锚点跟随 + 派生值重算（顺序不可倒，锚点迁移依赖 merged_to 已写）
    anchors = sync_entity_anchors(db)
    refresh_counts(db)
    out["merged"] = merged
    out["anchors"] = anchors
    out["clusters_after"] = int(db.execute(text(
        "SELECT COUNT(*) FROM pmwb_complaint_rootcause WHERE status IN ('open','candidate')"
    )).scalar() or 0)
    return out


def closing_check(db: Session) -> Dict[str, Any]:
    """簇闭合校验：**簇成员汇总 必须等于 指向活簇的工单指针数**。

    口径说明（2026-11-04 对齐）：
      - disabled（人工停用）簇的存量指针**合法保留**，不算悬空；
      - merged 簇的指针必须已迁到终簇，残留才算悬空（sync_entity_anchors 漏做）；
      - insufficient（信息不足）单历史上也进簇，此处只做计数提示，不参与闭合判定。
    """
    assigned = db.execute(text(
        "SELECT COUNT(*) FROM pmwb_complaint_ticket t "
        "JOIN pmwb_complaint_rootcause r ON r.rootcause_no = t.rootcause_no "
        "WHERE r.status IN ('open','candidate')"
    )).scalar() or 0
    summed = db.execute(text(
        "SELECT COALESCE(SUM(ticket_cnt), 0) FROM pmwb_complaint_rootcause "
        "WHERE status IN ('open','candidate')"
    )).scalar() or 0
    dangling = db.execute(text(
        "SELECT COUNT(*) FROM pmwb_complaint_ticket t "
        "LEFT JOIN pmwb_complaint_rootcause r ON r.rootcause_no = t.rootcause_no "
        "WHERE t.rootcause_no IS NOT NULL AND t.rootcause_no != '' "
        "AND (r.rootcause_no IS NULL OR r.status = 'merged')"
    )).scalar() or 0
    disabled_ptr = db.execute(text(
        "SELECT COUNT(*) FROM pmwb_complaint_ticket t "
        "JOIN pmwb_complaint_rootcause r ON r.rootcause_no = t.rootcause_no "
        "WHERE r.status = 'disabled'"
    )).scalar() or 0
    insuff = db.execute(text(
        "SELECT COUNT(*) FROM pmwb_complaint_ticket WHERE rc_status = :st "
        "AND rootcause_no IS NOT NULL AND rootcause_no != ''"
    ), {"st": RC.RC_STATUS_INSUFFICIENT}).scalar() or 0
    return {"assigned": int(assigned), "cluster_sum": int(summed or 0),
            "diff": int(assigned) - int(summed or 0),
            "dangling": int(dangling), "disabled_pointer": int(disabled_ptr),
            "insufficient_in_cluster": int(insuff),
            "balanced": int(assigned) == int(summed or 0) and int(dangling) == 0}


# 高危机制：涉及资金/合规/批量的，单量再小也不并入兜底（方案 §5.4 第 5 条「永不淘汰」）
HIGH_RISK_MECHANISMS: Tuple[str, ...] = (
    "计费错误", "未级联", "脏数据残留", "重复开通", "校验拦截",
)


def merge_long_tail(db: Session, max_cnt: int = 1, dry_run: bool = True) -> Dict[str, Any]:
    """长尾归并（方案 §5.4 降级第 1 条）：单量 ≤ max_cnt 且机制非高危的簇，
    并入同（环节 × 机制）的「其他」兜底簇。

    只压簇数、不丢单量：兜底簇承接全部成员，单量、周轨迹、问题锚点都随指针迁移。
    """
    rows = db.execute(text(
        "SELECT rootcause_no, pattern_key, fault_stage, mechanism, biz_object, ticket_cnt "
        "FROM pmwb_complaint_rootcause "
        "WHERE status IN ('open','candidate') AND pattern_key IS NOT NULL AND pattern_key != '' "
        "AND ticket_cnt <= :n ORDER BY pattern_key, id ASC"
    ), {"n": int(max_cnt)}).fetchall()

    # 按 (环节, 机制) 归组，找出需要下沉的簇
    sink: Dict[Tuple[str, str], List[str]] = {}
    for rc_no, key, st, mc, ob, cnt in rows:
        if mc in HIGH_RISK_MECHANISMS or mc == P.MECHANISM_CONSULT:
            continue          # 高危/咨询不参与长尾归并
        if (ob or "") == P.OBJECT_FALLBACK:
            continue          # 已经是兜底簇
        sink.setdefault((st, mc), []).append(rc_no)

    # 已有兜底簇先复用
    holders: Dict[Tuple[str, str], str] = {}
    for st, mc in sink:
        exist = find_by_key(db, P.pattern_key(st, mc, P.OBJECT_FALLBACK))
        if exist:
            holders[(st, mc)] = exist

    plan = [{"key": P.KEY_SEP.join((st, mc, P.OBJECT_FALLBACK)),
             "keep": holders.get((st, mc), ""),
             "absorb": nos,
             "new_holder": (st, mc) not in holders}
            for (st, mc), nos in sink.items()]
    absorb_total = sum(len(p["absorb"]) for p in plan)
    out: Dict[str, Any] = {
        "dry_run": dry_run, "max_cnt": int(max_cnt),
        "clusters_now": int(db.execute(text(
            "SELECT COUNT(*) FROM pmwb_complaint_rootcause "
            "WHERE status IN ('open','candidate')")).scalar() or 0),
        "groups": len(plan), "absorb_count": absorb_total,
        "protect_mechanisms": list(HIGH_RISK_MECHANISMS),
        "plan": plan[:60],
    }
    out["clusters_after_est"] = out["clusters_now"] - absorb_total + \
        sum(1 for p in plan if p["new_holder"])
    if dry_run:
        return out

    merged = 0
    for p in plan:
        keep = p["keep"]
        if not keep:
            st, mc = p["key"].split(P.KEY_SEP)[0], p["key"].split(P.KEY_SEP)[1]
            title = P.build_pattern(mc, P.OBJECT_FALLBACK)
            keep = _create_cluster(db, title, f"{st}环节下未单独成簇的零星个案（长尾归并）",
                                   [], stage=st, mechanism=mc,
                                   biz_object=P.OBJECT_FALLBACK)
        if not keep:
            continue
        marks = ",".join(f":a{i}" for i in range(len(p["absorb"])))
        params: Dict[str, Any] = {f"a{i}": v for i, v in enumerate(p["absorb"])}
        params.update({"keep": keep, "ts": datetime.now()})
        db.execute(text(
            f"UPDATE pmwb_complaint_ticket SET rootcause_no = :keep "
            f"WHERE rootcause_no IN ({marks})"), params)
        db.execute(text(
            f"UPDATE pmwb_complaint_rootcause SET status = 'merged', merged_to = :keep, "
            f"ticket_cnt = 0, updated_at = :ts WHERE rootcause_no IN ({marks})"), params)
        merged += len(p["absorb"])
        db.commit()
    anchors = sync_entity_anchors(db)
    refresh_counts(db)
    out["merged"] = merged
    out["anchors"] = anchors
    out["clusters_after"] = int(db.execute(text(
        "SELECT COUNT(*) FROM pmwb_complaint_rootcause "
        "WHERE status IN ('open','candidate')")).scalar() or 0)
    return out


def rekey_clusters(db: Session) -> Dict[str, Any]:
    """按当前 mechanism / biz_object / fault_stage 重算 pattern_key（纯规则、0 LLM）。

    派生字段必须有「从源重建」的路径：relabel 早期版本模型漏返 fault_stage 时
    会写下 mechanism 却不写 key，本函数把它补回来（也用于口径调整后的批量重算）。
    """
    rows = db.execute(text(
        "SELECT rootcause_no, fault_stage, mechanism, biz_object, pattern_key "
        "FROM pmwb_complaint_rootcause WHERE status IN ('open','candidate')"
    )).fetchall()
    fixed = cleared = retitled = 0
    for no, st, mc, ob, pk in rows:
        if not (st and mc and ob):
            if pk:
                db.execute(text(
                    "UPDATE pmwb_complaint_rootcause SET pattern_key = NULL, "
                    "updated_at = :ts WHERE rootcause_no = :no"),
                    {"no": no, "ts": datetime.now()})
                cleared += 1
            continue
        want = P.pattern_key(st, mc, ob)
        if want != (pk or ""):
            db.execute(text(
                "UPDATE pmwb_complaint_rootcause SET pattern_key = :pk, updated_at = :ts "
                "WHERE rootcause_no = :no"), {"pk": want, "no": no, "ts": datetime.now()})
            fixed += 1
        # 标题格式自愈：早期合并版本把 key 分隔符直接当标题（「环节-机制-对象」三段式）
        title = db.execute(text(
            "SELECT title FROM pmwb_complaint_rootcause WHERE rootcause_no = :no"
        ), {"no": no}).scalar() or ""
        if title and "（" not in title and len(title.split("-")) >= 3 and title != P.build_pattern(mc, ob):
            db.execute(text(
                "UPDATE pmwb_complaint_rootcause SET title = :t, updated_at = :ts "
                "WHERE rootcause_no = :no AND (source IS NULL OR source != 'manual')"
            ), {"t": P.build_pattern(mc, ob), "no": no, "ts": datetime.now()})
            retitled += 1
    db.commit()
    return {"scanned": len(rows), "fixed": fixed, "cleared": cleared,
            "retitled": retitled}


def cluster_health(db: Session) -> Dict[str, Any]:
    """簇健康度（看板数据源）：簇数 / 单簇率 / 覆盖率 / 未匹配率 / 咨询占比。"""
    total = db.execute(text("SELECT COUNT(*) FROM pmwb_complaint_rootcause "
                            "WHERE status IN ('open','candidate')")).scalar() or 0
    single = db.execute(text("SELECT COUNT(*) FROM pmwb_complaint_rootcause "
                             "WHERE status IN ('open','candidate') AND ticket_cnt <= 1"
                             )).scalar() or 0
    defect = db.execute(text("SELECT COUNT(*) FROM pmwb_complaint_rootcause "
                             "WHERE status IN ('open','candidate') AND is_defect = 1"
                             )).scalar() or 0
    # 覆盖率分母用「有根因文本的单」：insufficient 单也归了簇，若只算 ai/manual 会 >100%
    with_cause = db.execute(text(
        "SELECT COUNT(*) FROM pmwb_complaint_ticket "
        "WHERE root_cause IS NOT NULL AND root_cause != ''")).scalar() or 0
    in_cluster = db.execute(text(
        "SELECT COUNT(*) FROM pmwb_complaint_ticket t "
        "JOIN pmwb_complaint_rootcause r ON r.rootcause_no = t.rootcause_no "
        "WHERE r.status IN ('open','candidate')")).scalar() or 0
    fallback = db.execute(text(
        "SELECT COUNT(*) FROM pmwb_complaint_ticket t "
        "JOIN pmwb_complaint_rootcause r ON r.rootcause_no = t.rootcause_no "
        "WHERE r.status IN ('open','candidate') AND r.is_defect = 1 "
        "AND (r.biz_object = '其他' OR r.mechanism = '其他')"
    )).scalar() or 0
    state = P.cluster_count_state(int(total))
    return {
        "clusters": int(total), "defect_clusters": int(defect),
        "single_cluster": int(single),
        "single_rate": round(single / total, 3) if total else 0.0,
        "coverage": round(int(in_cluster) / with_cause, 3) if with_cause else 0.0,
        "fallback_rate": round(int(fallback) / int(in_cluster), 3) if in_cluster else 0.0,
        "tickets_in_cluster": int(in_cluster), "tickets_with_cause": int(with_cause),
        # 簇数是「参考带」不是硬指标（2026-11-04 老大定调：方法对、按需增长）
        "cluster_state": state,
        "target_over": state == "fragmented",
        "targets": {"cluster_band_min": P.CLUSTER_BAND_MIN,
                    "cluster_band_max": P.CLUSTER_BAND_MAX,
                    "single_rate_max": P.SINGLE_CLUSTER_RATE_MAX,
                    "fallback_rate_max": P.MISMATCH_RATE_MAX},
    }


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


# ── 簇的人工维护（2026-11-04：按需动态维护，支持新业务/新场景）──────
# 设计边界：
#   · 环节 / 机制 必须落受控枚举（否则跨簇口径就散了）；
#   · **业务对象允许人工自由命名**——新业务（FTTO、安防、SaaS …）出现时，
#     先立簇再挂单，不用等改代码；AI 自动链路仍只允许枚举内（见 _ensure_cluster）；
#   · 改键（环节/机制/对象）后自动重算 pattern_key，并与现存活簇查重，
#     撞键时**不静默新建**，而是回冲突让前端决定「并入已有」还是「改对象」。
def _norm_stage(v: str) -> str:
    s = (v or "").strip()
    return s if s in P.STAGES else ""


def _free_object(v: str) -> str:
    """人工对象名：允许自由命名，只做长度与空值约束（AI 侧仍走 normalize_object）。"""
    return (v or "").strip()[:32]


def _cluster_brief(db: Session, rc_no: str) -> Dict[str, Any]:
    r = db.execute(text(
        "SELECT rootcause_no, title, ticket_cnt, status FROM pmwb_complaint_rootcause "
        "WHERE rootcause_no = :no"), {"no": rc_no}).first()
    if not r:
        return {}
    return {"rootcause_no": r[0], "title": r[1], "ticket_cnt": int(r[2] or 0), "status": r[3]}


def _key_conflict(db: Session, pkey: str, exclude: str = "") -> Dict[str, Any]:
    """同键存活簇（排除自身）——撞键时必须让人决定，不能静默造第二个。"""
    if not pkey:
        return {}
    r = db.execute(text(
        "SELECT rootcause_no, title, ticket_cnt FROM pmwb_complaint_rootcause "
        "WHERE pattern_key = :k AND status IN ('open','candidate') "
        "AND (:ex = '' OR rootcause_no != :ex) ORDER BY ticket_cnt DESC LIMIT 1"
    ), {"k": pkey, "ex": exclude or ""}).first()
    if not r:
        return {}
    return {"rootcause_no": r[0], "title": r[1], "ticket_cnt": int(r[2] or 0)}


def _sync_member_pattern(db: Session, rc_no: str, stage: str, mech: str,
                         obj: str, pattern: str) -> int:
    """簇级口径改了，成员工单的三要素要跟着对齐（报表按工单聚合才不会分叉）。

    只改 pattern 三要素，**不动 root_cause**（个案事实仍保留各自账号单号）。
    """
    n = db.execute(text(
        "UPDATE pmwb_complaint_ticket SET rc_mechanism = :mc, rc_object = :ob, "
        "root_pattern = :pt WHERE rootcause_no = :no"
    ), {"mc": mech, "ob": obj, "pt": pattern, "no": rc_no}).rowcount
    return int(n or 0)


def _move_ticket_nos(db: Session, ticket_nos: List[str], rc_no: str) -> int:
    """批量改指工单（不 commit、不重算，由调用方统一收尾）。"""
    moved = 0
    for no in ticket_nos:
        r = db.execute(text(
            "UPDATE pmwb_complaint_ticket SET rootcause_no = :rc WHERE ticket_no = :no"
        ), {"rc": rc_no, "no": str(no).strip()}).rowcount
        moved += int(r or 0)
    return moved


def create_cluster(db: Session, stage: str, mechanism: str, biz_object: str,
                   trigger: str = "", title: str = "", description: str = "",
                   fault_type: str = "", own_party: str = "",
                   fix_mode: str = "", is_defect: Optional[bool] = None,
                   ticket_nos: Optional[List[str]] = None) -> Dict[str, Any]:
    """人工新建根因簇（状态直接 open、source=manual，供新业务/新场景先立后挂）。

    撞键（同环节同机制同对象已有活簇）时返回 `conflict`，前端应提示并入。
    """
    st = _norm_stage(stage)
    mc = P.normalize_mechanism(mechanism)
    ob = _free_object(biz_object)
    if not st:
        return {"ok": False, "message": f"订单环节必须从受控枚举中选：{'、'.join(P.STAGES)}"}
    if not mc:
        return {"ok": False, "message": f"失败机制必须从受控枚举中选：{'、'.join(P.MECHANISMS)}"}
    if not ob:
        return {"ok": False, "message": "业务对象不能为空"}
    tg = (trigger or "").strip()[:32]
    pkey = P.pattern_key(st, mc, ob)
    conflict = _key_conflict(db, pkey)
    if conflict:
        return {"ok": False, "conflict": True,
                "message": f"该（{st} × {mc} × {P.upper_object(ob) or ob}）已有簇 "
                           f"{conflict['rootcause_no']}（{conflict['ticket_cnt']} 单），请直接并入",
                "existing": conflict}
    pat = (title or "").strip() or P.build_pattern(mc, ob, tg)
    if P.pattern_violations(pat):
        pat = P.build_pattern(mc, ob)          # 去 trigger 再试
    bad = P.pattern_violations(pat)
    if bad:
        return {"ok": False, "message": "簇标题不合规：" + "；".join(bad)}
    if is_defect is None:
        is_defect = mc != P.MECHANISM_CONSULT
    rc_no = _next_rc_no(db)
    db.execute(text(
        "INSERT INTO pmwb_complaint_rootcause "
        "(rootcause_no, title, description, fault_stage, mechanism, biz_object, "
        " pattern_key, fault_type, own_party, fix_mode, is_defect, status, source, "
        " ticket_cnt, sample_tickets, created_at, updated_at) "
        "VALUES (:no, :title, :desc, :st, :mc, :ob, :pk, :ft, :op, :fm, :df, "
        " 'open', 'manual', 0, '[]', :ts, :ts)"
    ), {"no": rc_no, "title": pat, "desc": (description or "").strip()[:500],
        "st": st, "mc": mc, "ob": ob, "pk": pkey,
        "ft": fault_type if fault_type in RC.FAULT_TYPES else None,
        "op": own_party if own_party in RC.OWN_PARTIES else None,
        "fm": fix_mode if fix_mode in RC.FIX_MODES else None,
        "df": 1 if is_defect else 0, "ts": datetime.now()})
    moved = _move_ticket_nos(db, ticket_nos or [], rc_no)
    db.commit()
    refresh_counts(db)
    return {"ok": True, "rootcause_no": rc_no, "title": pat, "pattern_key": pkey,
            "moved": moved}


def update_cluster(db: Session, rc_no: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """人工编辑簇（含改键）。改键后自动重算 pattern_key 并查重，撞键回冲突。"""
    cur = db.execute(text(
        "SELECT title, description, fault_stage, mechanism, biz_object, fault_type, "
        "own_party, fix_mode, is_defect, status FROM pmwb_complaint_rootcause "
        "WHERE rootcause_no = :no"), {"no": rc_no}).first()
    if not cur:
        return {"ok": False, "message": "根因簇不存在"}
    (c_title, c_desc, c_stage, c_mech, c_obj, c_ftype, c_party, c_fix, c_df, c_status) = cur

    stage = _norm_stage(payload.get("fault_stage")) if payload.get("fault_stage") is not None \
        else (c_stage or "")
    mech = P.normalize_mechanism(payload.get("mechanism")) \
        if payload.get("mechanism") is not None else (c_mech or "")
    obj = _free_object(payload.get("biz_object")) \
        if payload.get("biz_object") is not None else (c_obj or "")
    trigger = payload.get("trigger")
    if not stage or not mech or not obj:
        return {"ok": False, "message": "环节 / 机制 / 业务对象都必须有值"}
    if not (c_stage and c_mech and c_obj):
        return {"ok": False, "message": "该簇缺少必要的模式要素（环节/机制/对象），请先补齐再改"}
    # 触发条件：显式传入优先；没传则沿用原标题括号内的限定语（避免改描述时丢掉它）
    if trigger is None:
        m = re.search(r"[（(]([^）)]{1,32})[）)]", c_title or "")
        tg = m.group(1).strip() if m else ""
    else:
        tg = str(trigger).strip()[:32]

    key_changed = (stage, mech, obj) != (c_stage, c_mech, c_obj)
    pkey = P.pattern_key(stage, mech, obj)
    if key_changed:
        conflict = _key_conflict(db, pkey, exclude=rc_no)
        if conflict:
            return {"ok": False, "conflict": True,
                    "message": f"目标键已存在簇 {conflict['rootcause_no']}"
                               f"（{conflict['ticket_cnt']} 单），请直接合并过去",
                    "existing": conflict}

    # 标题：显式传入优先；否则改键/改触发条件时按受控模式重建，其余情况保留人工命名
    new_title = (payload.get("title") or "").strip()[:200]
    if not new_title:
        if key_changed or trigger is not None:
            new_title = P.build_pattern(mech, obj, tg)
        else:
            new_title = c_title or P.build_pattern(mech, obj, tg)

    sets = ["title = :title", "fault_stage = :st", "mechanism = :mc", "biz_object = :ob",
            "pattern_key = :pk", "updated_at = :ts"]
    params: Dict[str, Any] = {"title": new_title, "st": stage, "mc": mech, "ob": obj,
                              "pk": pkey, "no": rc_no, "ts": datetime.now()}
    if payload.get("description") is not None:
        sets.append("description = :desc")
        params["desc"] = (payload.get("description") or "").strip()[:500]
    for fld, col, allowed in (("fault_type", "fault_type", RC.FAULT_TYPES),
                              ("own_party", "own_party", RC.OWN_PARTIES),
                              ("fix_mode", "fix_mode", RC.FIX_MODES)):
        if payload.get(fld) is not None:
            v = payload.get(fld)
            if v and v not in allowed:
                return {"ok": False, "message": f"{fld} 不在受控枚举内：{v}"}
            sets.append(f"{col} = :{fld}")
            params[fld] = v or None
    if payload.get("is_defect") is not None:
        sets.append("is_defect = :df")
        params["df"] = 1 if payload["is_defect"] else 0
    db.execute(text(
        f"UPDATE pmwb_complaint_rootcause SET {', '.join(sets)} WHERE rootcause_no = :no"
    ), params)
    synced = _sync_member_pattern(db, rc_no, stage, mech, obj,
                                  P.build_pattern(mech, obj, tg))
    db.commit()
    refresh_counts(db)
    return {"ok": True, "rootcause_no": rc_no, "title": new_title,
            "pattern_key": pkey, "key_changed": key_changed, "synced_tickets": synced}


def split_cluster(db: Session, src_no: str, ticket_nos: List[str],
                  target_no: str = "", new_cluster: Optional[Dict[str, Any]] = None
                  ) -> Dict[str, Any]:
    """把簇内部分工单拆出去：并入 target_no，或按 new_cluster 新建一个簇。"""
    src = _cluster_brief(db, src_no)
    if not src:
        return {"ok": False, "message": "源根因簇不存在"}
    nos = [str(x).strip() for x in (ticket_nos or []) if str(x).strip()]
    if not nos:
        return {"ok": False, "message": "请至少选择一个工单"}
    valid = set()
    rows = db.execute(text(
        "SELECT ticket_no FROM pmwb_complaint_ticket WHERE rootcause_no = :no"
    ), {"no": src_no}).fetchall()
    valid = {r[0] for r in rows}
    bad = [n for n in nos if n not in valid]
    if bad:
        return {"ok": False, "message": f"以下工单不在该簇内：{'、'.join(bad[:5])}"}

    if target_no:
        if target_no == src_no:
            return {"ok": False, "message": "不能拆到自身"}
        dst = _cluster_brief(db, target_no)
        if not dst:
            return {"ok": False, "message": "目标根因簇不存在"}
        moved = _move_ticket_nos(db, nos, target_no)
        db.commit()
        refresh_counts(db)
        return {"ok": True, "action": "move", "target_no": target_no, "moved": moved}

    nc = new_cluster or {}
    res = create_cluster(db, nc.get("fault_stage") or "", nc.get("mechanism") or "",
                         nc.get("biz_object") or "", trigger=nc.get("trigger") or "",
                         title=nc.get("title") or "", description=nc.get("description") or "",
                         fault_type=nc.get("fault_type") or "",
                         own_party=nc.get("own_party") or "",
                         fix_mode=nc.get("fix_mode") or "",
                         ticket_nos=nos)
    if not res.get("ok"):
        return res
    res["action"] = "split"
    res["src_no"] = src_no
    return res


def move_tickets(db: Session, ticket_nos: List[str], target_no: str) -> Dict[str, Any]:
    """批量把工单改指到指定簇（人工纠偏用；不新建簇）。"""
    dst = _cluster_brief(db, target_no)
    if not dst:
        return {"ok": False, "message": "目标根因簇不存在"}
    nos = [str(x).strip() for x in (ticket_nos or []) if str(x).strip()]
    if not nos:
        return {"ok": False, "message": "请至少选择一个工单"}
    moved = _move_ticket_nos(db, nos, target_no)
    db.commit()
    refresh_counts(db)
    return {"ok": True, "moved": moved, "target_no": target_no}


def list_clusters(db: Session, status: str = "", keyword: str = "",
                  page: int = 1, page_size: int = 50) -> Dict[str, Any]:
    """根因库列表（候选在前，按单量降序）。

    默认只列**在册簇**：`merged` 是 merge 留下的墓碑行（ticket_cnt=0，只服务于
    merged_to 链追溯），若一并列出，页面「根因簇」条数会虚高——实测 1103 行里
    867 行是墓碑，真实在册簇仅 236 个。要看已合并的，显式传 status=merged。
    """
    where = ["1 = 1"]
    params: Dict[str, Any] = {}
    if status:
        where.append("status = :st")
        params["st"] = status
    else:
        where.append("status <> :nst")
        params["nst"] = RC.RC_LIB_MERGED
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
        "last_week, merged_to, updated_at, mechanism, biz_object, pattern_key, is_defect "
        f"FROM pmwb_complaint_rootcause WHERE {w} "
        "ORDER BY CASE status WHEN 'candidate' THEN 0 WHEN 'open' THEN 1 "
        "  WHEN 'disabled' THEN 2 ELSE 3 END, ticket_cnt DESC, id ASC "
        "LIMIT :lim OFFSET :off"
    ), params).fetchall()
    # 状态分布（全库，不受筛选影响）：live_total 与 KPI 卡同口径，merged 单列供追溯提示
    counts = {str(k): int(v) for k, v in db.execute(text(
        "SELECT status, COUNT(*) FROM pmwb_complaint_rootcause GROUP BY status")).fetchall()}
    merged_total = counts.get(RC.RC_LIB_MERGED, 0)
    live_total = sum(v for k, v in counts.items() if k != RC.RC_LIB_MERGED)
    return {
        "total": int(total), "page": int(page), "page_size": int(page_size),
        "live_total": int(live_total), "merged_total": int(merged_total),
        "counts": counts,
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
            "mechanism": r[16] or "", "biz_object": r[17] or "",
            "pattern_key": r[18] or "", "is_defect": int(r[19] or 1),
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
        "own_party, fix_mode, status, ticket_cnt, sample_tickets, first_week, last_week, "
        "mechanism, biz_object, pattern_key "
        "FROM pmwb_complaint_rootcause WHERE rootcause_no = :no"
    ), {"no": rc_no}).first()
    if not r:
        return None
    tickets = db.execute(text(
        "SELECT ticket_no, week, city, LEFT(root_cause, 200), rc_status, rc_confidence, "
        "root_pattern "
        "FROM pmwb_complaint_ticket WHERE rootcause_no = :no ORDER BY id DESC LIMIT 50"
    ), {"no": rc_no}).fetchall()
    return {
        "rootcause_no": r[0], "title": r[1], "description": r[2] or "",
        "fault_stage": r[3] or "", "fault_system": r[4] or "", "fault_type": r[5] or "",
        "own_party": r[6] or "", "fix_mode": r[7] or "", "status": r[8],
        "status_label": RC.RC_LIB_STATUS_LABELS.get(r[8], r[8]),
        "ticket_cnt": int(r[9] or 0), "sample_tickets": json.loads(r[10] or "[]"),
        "first_week": r[11] or "", "last_week": r[12] or "",
        "mechanism": r[13] or "", "biz_object": r[14] or "", "pattern_key": r[15] or "",
        "tickets": [{"ticket_no": t[0], "week": t[1] or "", "city": t[2] or "",
                     "root_cause": t[3] or "", "rc_status": t[4] or "",
                     "rc_confidence": float(t[5] or 0),
                     "root_pattern": t[6] or ""} for t in tickets],
    }
