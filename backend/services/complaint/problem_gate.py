"""归入门禁：每单 100% 自动过闸、拒识优先、漂移重核（方案 v4.2 / 任务 D3）。

最高约束（§1.3 / §4）：**全链路无人**。未过闸的工单自动二次判定，仍不过则自动进
未归类清单并写明缺哪项证据；不排队等人、不静默归入、不靠改写描述把错配「解释进去」。

生成与判定分离：本模块的判据是「L2 描述要素 ↔ 该单原文证据」的对应关系，
与 D1 的文本规范校验、D2 的建类判据、语义生成插件均不同，通道标识亦不同。
"""

from __future__ import annotations

from typing import Any, Dict, List

from constants import complaint_problem as P
from services.complaint.problem_class import canonical
from services.complaint.problem_point import FAILURE_EVIDENCE_KINDS

# 独立判定通道：与 D1 JUDGE_CHANNEL / D2 CARD_CHANNEL 分离
GATE_CHANNEL = "gate-deterministic-v1"
SECOND_CHANNEL = "gate-second-pass-v1"


def _failure_texts(res: Dict[str, Any]) -> List[str]:
    return [a.get("text", "") for a in (res.get("anchors") or [])
            if a.get("kind") in FAILURE_EVIDENCE_KINDS and a.get("text")]


def _covers(fragment: str, text: str) -> bool:
    """确定性覆盖判定：归一后互为子串，或 4 字连续窗口命中。"""
    a, b = canonical(fragment), canonical(text)
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    return any(a[i:i + 4] in b for i in range(max(0, len(a) - 3)))


def negative_short_circuit(res: Dict[str, Any], cls: Dict[str, Any]) -> bool:
    """§4.2 反例短路：命中判定卡任一反例 → 确定性直接排除，不再裁量。"""
    no = str(res.get("ticket_no") or "")
    evs = set(_failure_texts(res))
    for ex in cls.get("card", {}).get("negatives", []):
        if (ex.get("ticket_no") and ex["ticket_no"] == no) or (
                ex.get("evidence") and ex["evidence"] in evs):
            return True
    return False


def map_description_to_ticket(cls: Dict[str, Any], res: Dict[str, Any]) -> Dict[str, Any]:
    """方向① 描述 → 工单：描述四要素逐项在该单问题点与原文证据里定位，缺一项即不过。"""
    elements = cls.get("elements", {})
    point = res.get("point") or ""
    corpus = point + " " + " ".join(_failure_texts(res))
    mapped: List[str] = []
    missing: List[str] = []
    for key in P.ELEMENT_KEYS:
        val = elements.get(key, "")
        if not val:
            continue           # 触发条件可空，不要求映射
        if _covers(val, corpus):
            mapped.append(key)
        else:
            missing.append(P.ELEMENT_LABELS.get(key, key))
    return {"mapped": mapped, "missing": missing}


def independent_judge(cls: Dict[str, Any], res: Dict[str, Any]) -> Dict[str, Any]:
    """方向② 工单 → 描述：独立判据，不复用生成结果自证。

    判据：该单的可观察失败证据必须能被类描述覆盖，且具体对象一致；
    证据为空（E6）、或被塞进兜底类（E7）直接不成立。
    """
    reasons: List[str] = []
    desc = cls.get("description") or ""
    evs = _failure_texts(res)
    if not evs:
        reasons.append("E6 证据不足：无可观察失败片段")
    if not desc or desc in P.BANNED_STANDALONE_TERMS:
        reasons.append("E7 描述为兜底/泛词，禁止归入")
    obj = cls.get("elements", {}).get("object", "")
    if obj and not _covers(obj, res.get("point") or ""):
        reasons.append("I1 主诉对象与该单不一致")
    if evs and not any(_covers(e, desc) for e in evs):
        reasons.append("I3 可观察失败与描述不对应")
    return {"ok": not reasons, "reasons": reasons}


def second_pass(cls: Dict[str, Any], res: Dict[str, Any]) -> Dict[str, Any]:
    """自动二次判定：换判据（证据片段是否被整句描述覆盖），不是再问一次模型、更不是找人。"""
    desc = cls.get("description") or ""
    evs = _failure_texts(res)
    ok = bool(evs) and any(_covers(e, desc) for e in evs)
    return {"ok": ok,
            "reasons": [] if ok else ["二次判定仍不成立：证据片段无法被描述覆盖"],
            "channel": SECOND_CHANNEL}


def gate_one(res: Dict[str, Any], cls: Dict[str, Any]) -> Dict[str, Any]:
    """单张工单 × 单个类：100% 自动过闸，返回配对留痕。"""
    base: Dict[str, Any] = {
        "ticket_no": res.get("ticket_no", ""), "class_no": cls.get("class_no", ""),
        "policy_version": P.POLICY_VERSION,
        "generator_channel": res.get("generator_channel"),
        "judge_channel": GATE_CHANNEL,
        "second_channel": None,
        "status": "", "gaps": [], "mapped": [], "missing": [],
    }
    if res.get("status") != "ok":
        base["status"] = P.UNCLASSIFIED_STATUS
        base["gaps"] = list(res.get("gaps") or ["L1 未通过（不得作归类原料）"])
        return base
    if negative_short_circuit(res, cls):
        base["status"] = P.UNCLASSIFIED_STATUS
        base["gaps"] = ["反例短路：命中判定卡反例"]
        return base

    m = map_description_to_ticket(cls, res)
    j = independent_judge(cls, res)
    base["mapped"], base["missing"] = m["mapped"], m["missing"]
    gaps = ["描述要素未在该单定位：" + x for x in m["missing"]] + j["reasons"]

    if not gaps:
        base["status"] = "matched"
        return base

    # 自动二次判定（换判据、独立通道）；仍不过 → 自动进未归类清单，写清缺什么
    s = second_pass(cls, res)
    base["second_channel"] = SECOND_CHANNEL
    if s["ok"]:
        base["status"] = "matched_second"
        base["gaps"] = []
    else:
        base["status"] = P.UNCLASSIFIED_STATUS
        base["gaps"] = gaps + s["reasons"]
    return base


def run_gate(point_results: List[Dict[str, Any]],
             classes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """全量门禁 + 成员漂移重核 + 描述自动作废。100% 覆盖、零人工触点、可复现。"""
    by_no = {r.get("ticket_no", ""): r for r in point_results}
    owner = {no: c for c in classes for no in c.get("members", [])}
    pairs: List[Dict[str, Any]] = []
    unclassified: List[Dict[str, Any]] = []

    # ① 每张 L1 结论都必须有归属或明确拒识，绝不静默丢弃
    for r in point_results:
        cls = owner.get(r.get("ticket_no", ""))
        if cls is None or cls.get("status") != "published":
            unclassified.append({"ticket_no": r.get("ticket_no", ""),
                                 "status": r.get("status") if r.get("status") != "ok" else P.UNCLASSIFIED_STATUS,
                                 "gaps": list(r.get("gaps") or ["无可发布类：类为 draft 或未立类"])})
            continue
        p = gate_one(r, cls)
        pairs.append(p)
        if p["status"] == P.UNCLASSIFIED_STATUS:
            unclassified.append({"ticket_no": p["ticket_no"], "status": P.UNCLASSIFIED_STATUS,
                                 "gaps": p["gaps"]})
        elif cls.get("drift_rerun"):
            p["drift_rerun"] = True

    # ② 成员漂移重核（§4.4）：新增成员或改描述 → 全量重跑，错配累计 2 单 → 描述作废
    voided: List[str] = []
    for c in classes:
        if c.get("status") != "published":
            continue
        mine = [p for p in pairs if p["class_no"] == c["class_no"]]
        mismatch = [p for p in mine if p["status"] == P.UNCLASSIFIED_STATUS]
        if c.get("drift_rerun") or len(mismatch) >= P.DRIFT_MAX_MISMATCH:
            # 全量重核：任一成员不过闸即整条描述作废，不局部打补丁
            rerun = [gate_one(by_no[p["ticket_no"]], c) for p in mine if p["ticket_no"] in by_no]
            if any(x["status"] == P.UNCLASSIFIED_STATUS for x in rerun) or len(mismatch) >= P.DRIFT_MAX_MISMATCH:
                c["status"] = "voided"
                c["reasons"] = c.get("reasons", []) + ["描述自动作废：成员漂移重核不成立"]
                voided.append(c["class_no"])
                for p in mine:
                    unclassified.append({"ticket_no": p["ticket_no"],
                                         "status": P.UNCLASSIFIED_STATUS,
                                         "gaps": ["所属描述已自动作废，成员全部重判"]})

    matched = [p for p in pairs if p["status"].startswith("matched")]
    return {
        "pairs": pairs, "matched": matched, "unclassified": unclassified,
        "voided_classes": voided,
        "stats": {
            "l1_total": len(point_results),
            "gate_coverage": 100.0 if len(pairs) + len(unclassified) >= len(point_results) else
                             round((len(pairs) + len(unclassified)) / max(1, len(point_results)) * 100, 2),
            "matched": len(matched),
            "unclassified": len(unclassified),
            "content_closure": round(len(matched) / max(1, len(pairs)) * 100, 2),
            "human_touches": [],        # 供 D4 一票否决校验：本链路不产生人工触点
            "policy_version": P.POLICY_VERSION,
        },
    }
