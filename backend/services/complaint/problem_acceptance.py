"""自动验收闸门、金标集回归与可复现校验（方案 v4.2 / 任务 D4）。

最高约束（§1.3 / §5）：所有指标由系统计算，**不设人工填报**；不达标由自动闸门拦截
（整期或该类不发布），不是退回人工重判，也不以「让人再看一眼」作为补救。

六项一票否决（无人工触点 / 逐单合格率 / 门禁覆盖 / 判定卡完备 / 证据锚点 / 生成判定分离）
任一不达标即整体不发布；数量闭合达标而内容闭合不达标，一律不通过。

可复现率不是自证：本模块把纯判定内核（D2 建类 + D3 门禁）按同输入跑两遍，
用结果签名比对得出，签名不同即 0 分。
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Dict, List, Optional

from constants import complaint_problem as P
from services.complaint.problem_class import build_classes, validate_card
from services.complaint.problem_gate import GATE_CHANNEL, run_gate, _covers


def _signature(obj: Any) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def run_pipeline_once(point_results: List[Dict[str, Any]], **kw) -> Dict[str, Any]:
    """一次纯判定内核执行（无写库、无随机、无时间戳），供两遍比对。"""
    built = build_classes(point_results, **kw)
    gated = run_gate(point_results, built["published"])
    return {"classes": built["classes"], "published": built["published"],
            "unclassified": built["unclassified"], "stats": built["stats"],
            "gate": gated}


def _pct(num: int, den: int) -> float:
    return round(num / den * 100, 2) if den else 0.0


def auto_sample(gate: Dict[str, Any], classes: List[Dict[str, Any]],
                n: int = P.WEEKLY_SAMPLE_SIZE) -> Dict[str, Any]:
    """自动分层抽样测漏判：用**第三套判据**（描述是否覆盖该单证据 + 描述合规）复核。

    抽样只用来量门禁有没有失灵，不承担「发现错配」的职责；不合格项自动回写为反例。
    """
    pairs = gate.get("matched", [])
    cls_by_no = {c["class_no"]: c for c in classes}
    # 分层：首现类 → 其它，按单号确定性排序（可复现）
    ordered = sorted(pairs, key=lambda p: (
        0 if cls_by_no.get(p["class_no"], {}).get("first_sight") else 1,
        str(p.get("ticket_no", ""))))
    sample = ordered[:n]
    leaks: List[str] = []
    for p in sample:
        c = cls_by_no.get(p["class_no"])
        if not c:
            continue
        desc = c.get("description", "")
        checked = P.check_description(desc)
        # 独立第三判据：描述必须覆盖该单至少一条证据片段，且自身合规
        res_anchor_ok = any(_covers(a.get("text", ""), desc)
                            for a in p.get("_anchors", [])) if p.get("_anchors") else True
        if not checked["ok"] or not res_anchor_ok:
            leaks.append(p["ticket_no"])
    rate = _pct(len(leaks), len(sample))
    return {"sample_size": len(sample), "leaks": leaks, "leak_rate": rate,
            "note": "抽样测漏判，不承担发现错配职责"}


def rewrite_negatives(classes: List[Dict[str, Any]], leaks: List[str],
                      point_results: List[Dict[str, Any]]) -> int:
    """§4.4 漏判自动回写为判定卡反例（反例随版本累积，门禁逐期变严）。"""
    by_no = {r.get("ticket_no", ""): r for r in point_results}
    added = 0
    for c in classes:
        card = c.get("card", {})
        negs = card.setdefault("negatives", [])
        have = {x.get("ticket_no") for x in negs}
        for no in leaks:
            if no in have:
                continue
            r = by_no.get(no, {})
            anchors = [a.get("text", "") for a in (r.get("anchors") or []) if a.get("text")]
            negs.append({"ticket_no": no, "evidence": anchors[0] if anchors else "",
                         "reason": "抽样漏判自动回写", "exclude_code": "E3"})
            added += 1
    return added


def build_goldset(gate: Dict[str, Any], classes: List[Dict[str, Any]],
                  leaks: List[str]) -> Dict[str, Any]:
    """金标集自动构建与滚动扩充：核心集 + 新立类 + 争议单 + 漏判单，无人工标注。"""
    core: List[str] = []
    for p in gate.get("matched", []):
        if p["ticket_no"] not in core:
            core.append(p["ticket_no"])
        if len(core) >= P.GOLDSET_CORE_SIZE:
            break
    new_classes = [c["class_no"] for c in classes if c.get("first_sight")]
    disputes = [u["ticket_no"] for u in gate.get("unclassified", [])][:P.GOLDSET_CORE_SIZE]
    extra = [x for x in new_classes + disputes + leaks if x not in core]
    return {"core": core, "added": extra,
            "new_class_coverage": _pct(len(new_classes), max(1, len(new_classes))),
            "policy_version": P.POLICY_VERSION}


def compute_metrics(point_results: List[Dict[str, Any]], classes: List[Dict[str, Any]],
                    gate: Dict[str, Any], sample: Dict[str, Any],
                    reproducible: float, goldset: Dict[str, Any]) -> Dict[str, float]:
    """§5 全指标（键名与 P.ACCEPTANCE 一一对应，阈值只有一处定义）。"""
    total = len(point_results)
    ok_l1 = [r for r in point_results if r.get("status") == "ok"]
    pairs = gate.get("pairs", [])
    matched = gate.get("matched", [])
    published = [c for c in classes if c.get("status") == "published"]
    by_no = {r.get("ticket_no", ""): r for r in point_results}

    # §5 分母澄清（2026-11-05，与方案「未归类率 / 已分析单量」对齐）：
    # 「待自动补跑」= 分析未完成，不进任何质量指标的分母，但由 analysis_coverage
    # 单独约束；「证据不足自动拒识」= 已分析且无问题点可写，不进合格率分母，
    # 仍如实计入未归类率。两者都不隐藏、不塞进兜底类。
    pending_nos = {r.get("ticket_no") for r in point_results
                   if r.get("status") == P.DEGRADED_STATUS}
    evidence_nos = {r.get("ticket_no") for r in point_results
                    if P.DEGRADED_REASON_EVIDENCE in (r.get("gaps") or [])}
    analyzed = total - len(pending_nos)
    analyzable = total - len(pending_nos | evidence_nos)
    unc = [u for u in gate.get("unclassified", [])
           if u.get("ticket_no") not in pending_nos]
    matched_done = [p for p in matched if p.get("ticket_no") not in pending_nos]
    # §2.5「写不出问题点的单不得计入任何问题点类」：合格率的分子分母都只取
    # **已写出并作为归类原料**的逐单记录；写不出的单不藏在合格率里，而是
    # 由未归类率 / 自动拒识率 / 证据不足率三个独立指标如实约束。
    written = [r for r in point_results
               if (r.get("point") or "").strip()
               and r.get("status") != P.DEGRADED_STATUS]
    auto_reject_nos = {r.get("ticket_no") for r in point_results
                       if r.get("status") == P.UNCLASSIFIED_STATUS
                       and any("自动拒识" in g for g in (r.get("gaps") or []))}
    unc_for_rate = {u.get("ticket_no") for u in unc} - evidence_nos

    # 无人工触点：结果里不得出现任何人判字段，且门禁不得产生人工触点
    blob = json.dumps({"g": gate.get("stats", {}), "p": pairs}, ensure_ascii=False, default=str)
    clean = (not gate["stats"].get("human_touches") and
             not any(k in blob for k in P.FORBIDDEN_HUMAN_TOUCHES))
    separation_ok = all(p.get("judge_channel") == GATE_CHANNEL and
                        p.get("generator_channel") != GATE_CHANNEL for p in pairs)
    evidence_ok = all(bool(by_no.get(p["ticket_no"], {}).get("anchors")) for p in pairs)
    one_to_one = len({p["ticket_no"] for p in pairs}) == len(pairs)

    overwide = sum(1 for p in pairs if "描述要素未在该单定位" in " ".join(p.get("gaps", [])))
    mispoint = sum(1 for p in pairs if "主诉对象与该单不一致" in " ".join(p.get("gaps", [])))
    hardstuff = sum(1 for c in classes if c.get("description") in P.BANNED_STANDALONE_TERMS)

    m: Dict[str, float] = {
        "no_human_touch": 100.0 if clean else 0.0,
        "point_pass_rate": _pct(sum(1 for r in written if r["status"] == "ok"), len(written)),
        "analysis_coverage": _pct(analyzed, total),
        "auto_reject_max": _pct(len(auto_reject_nos), analyzable),
        "evidence_missing_rate": _pct(len(evidence_nos), analyzed),  # 观测，不设硬线
        "gate_coverage": float(gate["stats"].get("gate_coverage", 0.0)),
        "card_complete": _pct(sum(1 for c in published if validate_card(c["card"])["ok"]),
                              max(1, len(classes))),
        "evidence_anchor": 100.0 if evidence_ok and pairs else (0.0 if pairs else 100.0),
        "separation": 100.0 if separation_ok and pairs else (0.0 if pairs else 100.0),
        "reproducible": round(reproducible, 2),
        "desc_concrete": _pct(sum(1 for c in published if P.check_description(c["description"])["ok"]),
                              max(1, len(classes))),
        "accuracy": round(max(0.0, min(float(gate["stats"].get("content_closure", 0.0)),
                                       100.0 - sample["leak_rate"])), 2),
        "gate_leak_max": sample["leak_rate"],
        "overwide_max": _pct(overwide, max(1, len(pairs))),
        "mispoint_max": _pct(mispoint, max(1, len(pairs))),
        "hardstuff_max": float(hardstuff),
        "one_ticket_one_class": 100.0 if one_to_one else 0.0,
        "unclassified_max": _pct(len(unc_for_rate), analyzable),
        # 按单号去重：描述作废时同单会重复进未归类清单，不能算两次
        "count_closure": _pct(len({p["ticket_no"] for p in matched_done} |
                                  {u["ticket_no"] for u in unc}), analyzed),
        "content_closure": float(gate["stats"].get("content_closure", 0.0)),
        "head_rerun": 100.0 if all(not c.get("drift_rerun") or c.get("status") == "published"
                                   for c in classes) else 0.0,
        "drift_rerun": 100.0 if not gate.get("voided_classes") else 0.0,
        "first_sight_admission": 100.0 if all(c.get("card") for c in classes
                                              if c.get("first_sight")) else 0.0,
        "goldset_new_coverage": float(goldset["new_class_coverage"]),
        "representative_verifiable": 100.0 if all(c.get("card", {}).get("positives")
                                                  for c in published) else 0.0,
    }
    return m


def observation_warnings(metrics: Dict[str, float]) -> List[str]:
    """§5 观测指标：超标只如实标注，供状态页/汇总页展示（唯一实现，禁另造）。"""
    out: List[str] = []
    for key in P.OBSERVATION_KEYS:
        val, thr = metrics.get(key), P.ACCEPTANCE.get(key)
        if val is None or thr is None:
            continue
        ok = val <= thr if key.endswith("_max") else val >= thr
        sign = "≤" if key.endswith("_max") else "≥"
        if not ok:
            out.append(f"{key}={val}（观测线{sign}{thr}）：未归类清单已如实列出，需复核口径")
    return out


def decide(metrics: Dict[str, float]) -> Dict[str, Any]:
    """自动发布闸门：六项一票否决 + 硬门槛；观测指标只如实标注，不拦截。"""
    failed: List[str] = []
    veto: List[str] = []
    warnings: List[str] = observation_warnings(metrics)
    for key, threshold in P.ACCEPTANCE.items():
        val = metrics.get(key)
        if val is None:
            continue
        ok = val <= threshold if key.endswith("_max") else val >= threshold
        sign = "≤" if key.endswith("_max") else "≥"
        if key in P.OBSERVATION_KEYS:
            # §5「观测 + 禁止掩盖」：照实展示、逐单列缺口，不拦截也不压数值
            continue
        if not ok:
            failed.append(f"{key}={val}（要求{sign}{threshold}）")
            if key in P.VETO_KEYS:
                veto.append(key)
    # 数量闭合达标但内容闭合不达标，一律不通过（§5 必要但不充分）
    if (metrics.get("count_closure", 0) >= P.ACCEPTANCE["count_closure"] and
            metrics.get("content_closure", 0) < P.ACCEPTANCE["content_closure"]):
        failed.append("数量闭合达标但内容闭合不达标")
    return {"publish": not failed, "failed": failed, "veto": veto,
            "warnings": warnings, "policy_version": P.POLICY_VERSION}


def evaluate(point_results: List[Dict[str, Any]], **kw) -> Dict[str, Any]:
    """全链验收入口：两遍重跑测可复现 → 计算全指标 → 抽样测漏判 → 自动回写 → 闸门。"""
    first = run_pipeline_once(point_results, **kw)
    second = run_pipeline_once(point_results, **kw)
    sig1 = _signature({"classes": first["classes"], "stats": first["stats"],
                       "matched": [p["ticket_no"] for p in first["gate"]["matched"]]})
    sig2 = _signature({"classes": second["classes"], "stats": second["stats"],
                       "matched": [p["ticket_no"] for p in second["gate"]["matched"]]})
    reproducible = 100.0 if sig1 == sig2 else 0.0

    # 抽样复核需要该单证据锚点，临时挂到 pair 上（不写库、不改原结果）
    by_no = {r.get("ticket_no", ""): r.get("anchors", []) for r in point_results}
    for p in first["gate"]["matched"]:
        p["_anchors"] = by_no.get(p["ticket_no"], [])
    sample = auto_sample(first["gate"], first["classes"])
    added = rewrite_negatives(first["classes"], sample["leaks"], point_results) if sample["leaks"] else 0
    goldset = build_goldset(first["gate"], first["classes"], sample["leaks"])
    metrics = compute_metrics(point_results, first["classes"], first["gate"],
                              sample, reproducible, goldset)
    decision = decide(metrics)
    return {"metrics": metrics, "decision": decision, "sample": sample,
            "goldset": goldset, "reproducible": reproducible,
            "negatives_added": added, "classes": first["classes"],
            "gate": first["gate"], "policy_version": P.POLICY_VERSION}
