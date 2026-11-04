"""L2 问题点类：自动建类、结构化判定卡、拒识优先（方案 v4.2 / 任务 D2）。

最高约束（§1.3）：**不设人工编制环节**。描述与判定卡全部由系统依据成员工单的
共性证据自动生成；卡不全的类自动判 draft，不得发布，也不等人补。

与旧做法的本质区别：旧链路用「环节 × 机制 × 上位对象」三元组当名称，产出
「订单-未归档」这类抽象标签；本模块用四要素（具体对象 / 动作 / 可观察失败 / 触发条件）
作**归并判据**，名称则是一句具体投诉问题点，两者职责分离（方案 §0.2 成因①）。

类数无上限、无压缩、无兜底类；1 单也立类（首现）。正反例必须与真实工单和原文片段绑定。
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from constants import complaint_problem as P
from constants.complaint_pattern import OBJECTS
from services.complaint.problem_point import FAILURE_EVIDENCE_KINDS

# 生成通道标识（可插拔）；判定永远是确定性规则，与生成分离
CARD_CHANNEL = "deterministic-v1"

_PUNCT_RE = re.compile(r"[\s，,。.、；;：:！!？?「」『』\"'（）()\-－—|]+")
_DIGITS_RE = re.compile(r"\d{6,}")


def canonical(text: str) -> str:
    """§7.3 指称词表：只做拼写归一，不命名、不作键、不限制新对象。"""
    s = (text or "").strip()
    # 长词先替换，避免「施工工单」被「施工单」部分吃掉
    for src in sorted(P.TERM_SYNONYMS, key=len, reverse=True):
        s = s.replace(src, P.TERM_SYNONYMS[src])
    s = _DIGITS_RE.sub("", s)       # 单号/账号差异不因此拆类（§3.1 忽略差异）
    return _PUNCT_RE.sub("", s)


def strip_user_level(text: str) -> str:
    """L2 描述禁带用户级信息（§2.2）：确定性剥离，不改写语义。"""
    s = re.sub(r"1[3-9]\d{9}", "", text or "")
    s = re.sub(r"\d{8,}", "", s)
    s = re.sub(r"\d+\.\d{2}元|\d+元", "", s)
    return re.sub(r"\s{2,}", " ", s).strip()


# 主语前缀：抽对象时先剥掉，避免「客户申请」「一线查询」这类主语被当业务对象
_SUBJECT_PREFIXES: Tuple[str, ...] = (
    "客户", "一线", "用户", "装维", "营业员", "客户经理", "系统", "反馈",
    "反映", "表示", "要求", "咨询", "针对", "在", "因",
)


def _object_from_point(point: str) -> str:
    """词表未命中时，从 L1 原句确定性抽「具体对象」——只取原文出现过的字。

    不查第二份受控清单、不猜测语义、不限制新对象：新业务的对象原样进入四要素，
    写法差异仍由 canonical() 的拼写归一处理（§7.3 两层结构）。
    """
    s = strip_user_level((point or "").strip())
    for pref in sorted(_SUBJECT_PREFIXES, key=len, reverse=True):
        if s.startswith(pref):
            s = s[len(pref):]
            break
    hits = [(s.find(v), v) for v in P.APPEAL_VERBS if v in s]
    hits = [h for h in hits if h[0] >= 0]
    idx, verb = min(hits, key=lambda x: (x[0], -len(x[1]))) if hits else (0, "")
    tail = s[idx + len(verb):] if hits else s
    tail = re.split(r"[，,。.；;：:！!？?、|（）()]", tail)[0]
    tail = re.sub(r"^(的|了|在|把|将|给|为|对|向|从|以|中|时|后)+", "", tail)
    return tail[:8].strip()


def extract_elements(res: Dict[str, Any]) -> Dict[str, str]:
    """从 L1 结论里抽取四要素（机器可判，全部绑定证据片段，不靠语义猜测）。"""
    point = res.get("point") or ""
    anchors = res.get("anchors") or []
    failure_anchors = [a for a in anchors if a.get("kind") in FAILURE_EVIDENCE_KINDS]

    # 具体对象（§7.3 收口）：受控对象词表只作「常见写法的一致性提示」，
    # 不再是白名单、不再决定能否立类。未命中时从 L1 原句确定性抽取业务名词，
    # 因此新业务/新场景的对象不会被词表挡住，词表也不作类名。
    obj_hits = [o for o in OBJECTS if o in point]
    obj = max(obj_hits, key=len) if obj_hits else _object_from_point(point)

    # 动作：复用诉求动词，取最长命中
    act_hits = [v for v in P.APPEAL_VERBS if v in point]
    action = max(act_hits, key=len) if act_hits else ""

    # 可观察失败：优先取长度合规、能在原文定位的锚点片段
    usable = [a["text"] for a in failure_anchors if 6 <= len(a["text"]) <= 45]
    failure = max(usable, key=len) if usable else (
        max((a["text"] for a in failure_anchors), key=len, default=""))

    # 触发条件：字段/规则类片段中不在 failure 里重复的第一条
    triggers = [a["text"] for a in anchors
                if a.get("kind") in ("field", "rule_block") and a["text"] not in failure]
    trigger = triggers[0][:12] if triggers else ""

    return {"object": obj, "action": action, "failure": strip_user_level(failure),
            "trigger": strip_user_level(trigger)}


def _fit_description(text: str) -> str:
    """把 L1 句收敛成合规的 L2 一句描述：只做确定性截断，不改写语义、不臆造。"""
    s = strip_user_level((text or "").strip())
    if s and P.check_description(s)["ok"]:
        return s
    # 超长时按分句取能独立成立的最长前缀（仍是原文原词，不补字）
    cand = ""
    for part in re.split(r"[，,；;]", s):
        nxt = (cand + "，" + part) if cand else part
        if len(nxt) > P.DESC_HARD_MAX_CHARS:
            break
        cand = nxt
    return cand if cand and P.check_description(cand)["ok"] else ""


def compose_description(elements: Dict[str, str],
                        members: Optional[List[Dict[str, Any]]] = None) -> str:
    """由共性事实产出一句描述（确定性，不用枚举词拼接、不臆造）。

    D7 收口（2026-11-05 真实库诊断）：四要素用逗号机械拼成「施工单，申请，
    无法生成」是标签不是一句话，D0 必判不合格 → 类永远 draft、闸门永远不发布。
    本桶的成员四要素已全部相等（同一问题点），因此取**成员中第一条通过 D0
    校验的 L1 问题点句**作描述：它来自真实原文、具体、可复现，且仍须过 D3
    双向门禁与判定卡；若与任一成员证据不对应，描述由 D3 自动作废，不靠改写
    描述把错配「解释进去」。措辞不一致不再退回标签拼接，也不引入人工编制。
    """
    if members:
        pts = [strip_user_level((m.get("point") or "").strip())
               for m in members if isinstance(m, dict) and (m.get("point") or "").strip()]
        for cand in pts:
            fitted = _fit_description(cand)
            if fitted:
                return fitted
    obj, act, fail, trig = (elements.get(k, "") for k in P.ELEMENT_KEYS)
    parts: List[str] = []
    if trig and trig not in fail:
        parts.append(trig[:12])
    if obj and obj not in fail:
        parts.append(obj)
    if act and act not in fail and act not in obj:
        parts.append(act)
    if fail:
        parts.append(fail)
    desc = "，".join(p for p in parts if p)
    if len(desc) > P.DESC_HARD_MAX_CHARS:
        desc = desc[:P.DESC_HARD_MAX_CHARS].rstrip("，,。.、；;")
    return strip_user_level(desc)


def _example(res: Dict[str, Any], reason: str, exclude_code: str = "") -> Dict[str, str]:
    anchors = [a for a in (res.get("anchors") or [])
               if a.get("kind") in FAILURE_EVIDENCE_KINDS]
    ev = anchors[0]["text"] if anchors else ""
    return {"ticket_no": str(res.get("ticket_no") or ""), "evidence": ev,
            "reason": reason, "exclude_code": exclude_code}


def build_card(description: str, elements: Dict[str, str], fix_point: str,
               members: List[Dict[str, Any]], rejected_pool: List[Dict[str, Any]]) -> Dict[str, Any]:
    """自动生成结构化判定卡（§3.5）；正反例必须绑定真实工单与原文片段。

    首现类只有 1 张工单：正例取该单的不同原文片段；若只有一条片段，
    再取该单的逐单问题点作第二条可核依据（同一工单、两条不同依据，不编造工单）。
    """
    positives: List[Dict[str, str]] = []
    seen_ev = set()
    for m in members:
        for a in (m.get("anchors") or []):
            if a.get("kind") not in FAILURE_EVIDENCE_KINDS:
                continue
            ex = _example(m, "四要素全等且证据锚点成立")
            ex["evidence"] = a["text"]
            if ex["evidence"] in seen_ev:
                continue
            seen_ev.add(ex["evidence"])
            positives.append(ex)
            if len(positives) >= P.CARD_POSITIVE_MIN:
                break
        if len(positives) >= P.CARD_POSITIVE_MIN:
            break
    if len(positives) < P.CARD_POSITIVE_MIN and members:
        ex = _example(members[0], "逐单问题点原文，四要素全等")
        ex["evidence"] = (members[0].get("point") or "").strip()
        if ex["evidence"] and ex["evidence"] not in seen_ev:
            positives.append(ex)
    negatives: List[Dict[str, str]] = []
    neg_seen = set()
    for r in rejected_pool:
        if len(negatives) >= P.CARD_NEGATIVE_MIN:
            break
        ex = _example(r, "四要素不全等，按排除规则不得并入", "E3")
        if not ex["ticket_no"] or ex["ticket_no"] in neg_seen:
            continue
        neg_seen.add(ex["ticket_no"])
        negatives.append(ex)
    return {
        "description": description,
        "version": P.POLICY_VERSION,
        "effective_from": P.POLICY_VERSION,   # 口径版本即生效起点（不写时间戳，保证可复现）
        # 诉求动词未在原文词面命中时，用具体对象作可核依据（不编造主诉）
        "appeal": elements.get("action") or elements.get("object") or "",
        "breakpoint": elements.get("object", ""),
        "observable": elements.get("failure", ""),
        "fix_point": fix_point,
        "positives": positives,
        "negatives": negatives,
        "boundary": {
            "must_split": [r["code"] + " " + r["name"] for r in P.EXCLUDE_RULES],
            "ignorable": list(P.IGNORABLE_DIFFS),
            "unclassified": "证据不足或四要素不全 → 自动进未归类清单，不并入最近似类",
        },
        "card_channel": CARD_CHANNEL,
    }


def validate_card(card: Dict[str, Any]) -> Dict[str, Any]:
    """判定卡完备性（§5 一票否决）：缺任一项即不得发布，**不设人工补卡**。"""
    missing = [f for f in P.CARD_REQUIRED_FIELDS if not card.get(f)]
    if len(card.get("positives", [])) < P.CARD_POSITIVE_MIN:
        missing.append("positives >= 2")
    if len(card.get("negatives", [])) < P.CARD_NEGATIVE_MIN:
        missing.append("negatives >= 2")
    for ex in card.get("positives", []) + card.get("negatives", []):
        for f in P.CARD_EXAMPLE_FIELDS:
            if f not in ex:
                missing.append("example." + f)
    if P.is_vague_fix_point(card.get("fix_point", "")):
        missing.append("fix_point 不可指认")
    return {"ok": not missing, "missing": missing}


def admission_check(elements: Dict[str, str], fix_point: str,
                    members: List[Dict[str, Any]],
                    existing: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """§7.3 新类准入三问（全自动）。任一否 → 不立类，进未归类清单。"""
    failed: List[str] = []
    old_failures = {canonical(c.get("elements", {}).get("failure", ""))
                    for c in (existing or [])}
    if not canonical(elements.get("failure", "")) or canonical(elements.get("failure", "")) in old_failures:
        failed.append("A1 无旧类没有的新的可观察失败")
    if P.is_vague_fix_point(fix_point):
        failed.append("A2 修复落点不可指认")
    if not any(m.get("status") == "ok" and m.get("anchors") for m in members):
        failed.append("A3 无至少 1 张可完整举证的工单")
    return {"ok": not failed, "failed": failed}


def class_no(elements: Dict[str, str]) -> str:
    """确定性编号：同四要素 → 同编号，可复现、可全量重跑。"""
    raw = "|".join(canonical(elements.get(k, "")) for k in P.ELEMENT_KEYS)
    return "PP-" + hashlib.md5(raw.encode("utf-8")).hexdigest()[:8].upper()


def same_problem(a: Dict[str, str], b: Dict[str, str]) -> bool:
    """§3.1 四项全等（机器判据）：四要素归一后完全一致才允许归入。"""
    return all(canonical(a.get(k, "")) == canonical(b.get(k, "")) for k in P.ELEMENT_KEYS)


def build_classes(point_results: List[Dict[str, Any]], *,
                  generator: Optional[Callable[[List[Dict[str, Any]], Dict[str, str]], str]] = None,
                  fix_point_resolver: Optional[Callable[[Dict[str, str]], str]] = None,
                  existing: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """L1 结论 → 问题点类。拒识优先 → 准入三问 → 描述 → 判定卡 → 完备性闸门。

    语义生成通道（generator）可插拔；不可用时用确定性共性事实拼接，链路照常跑完，
    绝不排队等人。fix_point_resolver 未给定时按可观察失败推导一个**可指认**落点。
    """
    existing = list(existing or [])
    candidates: List[Dict[str, Any]] = []
    unclassified: List[Dict[str, Any]] = []
    for r in point_results:
        if r.get("status") == "ok" and r.get("point"):
            candidates.append(r)
        else:
            unclassified.append({"ticket_no": r.get("ticket_no", ""),
                                 "status": r.get("status", ""), "gaps": r.get("gaps", [])})

    # 四要素齐全才算「能判明问题点」，缺项自动拒识（不立兜底类、不近似并入）
    enriched: List[tuple] = []
    for r in candidates:
        el = extract_elements(r)
        if not el["object"] or not el["failure"]:
            unclassified.append({"ticket_no": r.get("ticket_no", ""),
                                 "status": P.UNCLASSIFIED_STATUS,
                                 "gaps": ["四要素不全：缺具体对象或可观察失败证据"]})
            continue
        enriched.append((r, el))

    # 四要素 canonical 拼接即归并键（与 same_problem 等价），用索引避免 O(n²) 全表比对；
    # 全量 1486 单跑两遍（D4 可复现校验）时这点很关键。
    def _key(e: Dict[str, str]) -> str:
        return "|".join(canonical(e.get(k, "")) for k in P.ELEMENT_KEYS)

    buckets: Dict[str, Dict[str, Any]] = {}
    existing_by_key = {_key(c["elements"]): c for c in existing}
    touched_existing: Dict[str, Dict[str, Any]] = {}
    for r, el in enriched:
        key = _key(el)
        in_existing = key in existing_by_key
        hit = existing_by_key.get(key) or buckets.get(key)
        if hit is not None:
            # 拒识优先：四要素全等 → 归入已有类，不立新类；新增成员触发漂移重核
            hit["drift_rerun"] = True
            if in_existing:
                # 已有类的 members 是工单号列表（沿用旧版描述/判定卡，不再重建）
                members = [m.get("ticket_no", "") if isinstance(m, dict) else m
                           for m in hit.get("members", [])]
                members.append(r.get("ticket_no", ""))
                hit["members"] = members
                touched_existing[key] = hit
            else:
                # 本批新类的 members 仍是 L1 结论 dict，供 build_card 取证据锚点
                hit["members"].append(r)
            continue
        buckets[key] = {"class_no": class_no(el), "elements": el, "members": [r],
                        "drift_rerun": False}

    rejected_pool = [r for r, _ in enriched]  # 其它桶的成员天然是最易混淆的反例来源
    out: List[Dict[str, Any]] = []
    for c in buckets.values():
        el = c["elements"]
        member_nos = {m.get("ticket_no", "") for m in c["members"]}
        peers = [r for r in rejected_pool if r.get("ticket_no", "") not in member_nos]
        fix_point = (fix_point_resolver(el) if fix_point_resolver
                     else "修复" + (el["failure"][:20] or "该问题点"))
        adm = admission_check(el, fix_point, c["members"], existing)
        if not adm["ok"]:
            for m in c["members"]:
                unclassified.append({"ticket_no": m.get("ticket_no", ""),
                                     "status": P.UNCLASSIFIED_STATUS, "gaps": adm["failed"]})
            continue
        desc = (generator(c["members"], el) if generator
                else compose_description(el, c["members"]))
        desc = strip_user_level((desc or "").strip())
        checked = P.check_description(desc)
        card = build_card(desc, el, fix_point, c["members"], peers)
        card_ok = validate_card(card)
        reasons: List[str] = []
        if not checked["ok"]:
            reasons.extend(checked["violations"])
        if not card_ok["ok"]:
            reasons.extend("CARD " + m for m in card_ok["missing"])
        out.append({
            "class_no": c["class_no"], "description": desc, "elements": el,
            "card": card, "members": [m.get("ticket_no", "") for m in c["members"]],
            "ticket_cnt": len(c["members"]), "fix_point": fix_point,
            "first_sight": len(c["members"]) <= P.FIRST_SIGHT_MIN_MEMBERS,
            "drift_rerun": c["drift_rerun"],
            "status": "published" if not reasons else "draft",
            "reasons": reasons, "policy_version": P.POLICY_VERSION,
        })

    # 归入已有类：描述与判定卡沿用旧版（不改口径），但成员增加触发 §4.4 漂移重核
    for c in touched_existing.values():
        out.append({
            **c,
            "status": c.get("status", "published"),
            "ticket_cnt": len(c.get("members", [])),
            "first_sight": False,
            "drift_rerun": True,
            "reasons": [],
        })

    published = [c for c in out if c["status"] == "published"]
    return {
        "classes": out,
        "published": published,
        "unclassified": unclassified,
        "stats": {"input": len(point_results), "candidates": len(candidates),
                  "classes": len(out), "published": len(published),
                  "first_sight": sum(1 for c in out if c["first_sight"]),
                  "unclassified": len(unclassified),
                  "policy_version": P.POLICY_VERSION},
    }
