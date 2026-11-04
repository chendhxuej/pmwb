"""L1 逐单投诉问题点：自动重写、证据锚点与独立判定（方案 v4.2 / 任务 D1）。

最高约束（§1.3）：分析过程不依赖人。本模块**不写库、不等人、不降级猜测**：
  - 生成通道（语义重写）是可插拔参数 generator；不可用时自动标 pending_auto_rerun
    并写明缺口，通道恢复后由编排层自动补跑，绝不转人工队列；
  - 判定通道固定为确定性规则 JUDGE_CHANNEL，与生成通道分离，生成结果必须重新过判；
  - 每个结论都绑定原文可指认片段（证据锚点），找不到片段即判不成立；
  - 同输入 + 同口径版本 → 同输出（结果里不含时间戳、不含随机数）。

存量数据的关键事实：现有 1476 条逐单记录里，含「非系统缺陷」154 条、含「属正常」66 条，
写的是「是否缺陷的结论」而不是客户在投诉什么（§2.5）。detect_conclusion_record 把它们
一律判为「未写出」，必须由系统回到原文自动重写后才能作为归类原料。
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from constants import complaint_problem as P

# 判定通道标识：随每条结论留痕；与生成通道不同，即「生成与判定分离」的可核验凭据
JUDGE_CHANNEL = "deterministic-v1"
MAX_EVIDENCE_SPANS = 16
ANCHOR_WINDOW = 4          # 证据片段中连续 4 字出现在问题点里，即视为锚定
EVIDENCE_TEXT_LIMIT = 6000  # 单侧原文截取上限（防超长，且保证可复现）

# 证据抽取规则（确定性、有序；不依赖语义通道）
_QUOTED_RE = re.compile(r"[「『\"']([^「」『』\"']{2,40})[」』\"']")
# 2026-11-05 真实库诊断：原文里「提交系统报错」「触发了审批拦截」「显示报错」等
# 此前完全抽不到片段，导致模型明明引用了原词仍被判 P02（无证据锚点）。
# 触发词只从 P.FAILURE_MARKERS 派生，不另造第二份清单。
_FAILURE_RE = re.compile(
    r"(?:显示|提示|报错|停在|处于|状态为|仍为|返回|拦截|阻断|受阻|卡在|超时|"
    r"未收到|收不到|查不到|搜不到|无法|不能|没有|失败|为空|空白|缺失|不一致|"
    r"未回传|未生成|未下发|未释放|未归档|未触发|未到账|未生效|未开通|无结果|"
    r"不支持|不允许|需先|请走|需走|被要求|被退回|驳回|不通过|无记录|查无|掉单|"
    r"审批拦截|走审批|退不了|办不了|回不了单|提交不了|多收费|不生效|重复)"
    r"[^，。；|\n]{0,24}"
)
# 句子级兜底片段：整句含失败词即整句作可指认证据，只用于 D1 锚点判定，
# 不参与 D2 的四要素/归并键（否则原文细微措辞差异会把同类拆散）。
_SENTENCE_RE = re.compile(r"[^，,。.；;！!？?\n|]+")
_SENTENCE_FAILURE_WORDS = tuple(w for w in P.FAILURE_MARKERS if len(w) >= 2)
_FIELD_RE = re.compile(r"[\u4e00-\u9fa5A-Za-z]{0,10}(?:字段|接口|报文|单号|编号|编码)[^，。；|\n]{0,12}")
_ID_RE = re.compile(r"\d{8,}")
# 咨询/规则类工单的「被什么规则挡住」（§2.5）：也算可观察事实，不算证据不足
_RULE_RE = re.compile(
    r"(?:请走|需按|必须|只能|不支持|暂不支持|无入口|无申请入口|无法申请|受限于|限制|"
    r"需等待|不允许|被拦截|被强制)[^，。；|\n]{0,24}"
)

_EVIDENCE_KINDS = ("error_text", "failure", "field", "rule_block", "identifier", "sentence")
# 能支撑「可观察失败/卡点」的证据类型；identifier 只作追溯锚点，不算依据
FAILURE_EVIDENCE_KINDS = ("error_text", "failure", "field", "rule_block")
# D1 专用：句子级片段也可作证据锚点（但 D2/D3 的四要素与门禁不用它）
POINT_FAILURE_KINDS = FAILURE_EVIDENCE_KINDS + ("sentence",)


def extract_evidence_spans(content: str, solution_history: str = "") -> List[Dict[str, Any]]:
    """从投诉原文与处理过程中抽取可指认片段（证据锚点原料）。

    返回 [{kind, text, source, start}]，按 source 顺序与位置排序、去重、限量，
    保证同输入必同输出。identifier 只作可追溯锚点，不算「可观察失败」依据。
    """
    out: List[Dict[str, Any]] = []
    seen = set()

    def _add(kind: str, frag: str, source: str, start: int) -> bool:
        frag = (frag or "").strip()
        # 同一段原文可能被多条规则命中（如「请走审批流程」既是规则阻断也是失败片段）：
        # 按 (类型, 文本) 去重，保留各类判据的独立留痕。
        key = (kind, frag)
        if not frag or key in seen:
            return False
        seen.add(key)
        out.append({"kind": kind, "text": frag, "source": source, "start": start})
        return len(out) >= MAX_EVIDENCE_SPANS

    for source, raw in (("content", content or ""), ("solution", solution_history or "")):
        s = raw[:EVIDENCE_TEXT_LIMIT]
        buckets: List[tuple] = []
        buckets.extend(("error_text", m) for m in _QUOTED_RE.finditer(s))
        buckets.extend(("failure", m) for m in _FAILURE_RE.finditer(s))
        buckets.extend(("field", m) for m in _FIELD_RE.finditer(s))
        buckets.extend(("rule_block", m) for m in _RULE_RE.finditer(s))
        for kind, m in sorted(buckets, key=lambda x: x[1].start()):
            frag = m.group(1) if kind == "error_text" else m.group(0)
            if _add(kind, frag, source, m.start()):
                return out
        # 句子级兜底：整句含失败词即作可指认片段，专治「提交系统报错」这类
        # 触发词在句末、精确正则只能抽到 2 个字的情况。
        for m in _SENTENCE_RE.finditer(s):
            seg = m.group(0).strip()
            if len(seg) < 4 or not any(w in seg for w in _SENTENCE_FAILURE_WORDS):
                continue
            if _add("sentence", seg[:45], source, m.start()):
                return out
        # 长编号只作追溯锚点，放最后且不作「可观察失败」依据
        for m in _ID_RE.finditer(s):
            if _add("identifier", m.group(0), source, m.start()):
                return out
    return out


def detect_conclusion_record(root_cause: str) -> Dict[str, Any]:
    """识别「结论式」存量逐单记录（§2.5）：写的是是否缺陷，不是投诉问题点。"""
    hits = P.conclusion_hits(root_cause or "")
    return {"is_conclusion": bool(hits), "hits": hits}


def anchor_hits(point: str, spans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """问题点里能定位到原文片段的锚点；用连续 4 字窗口，避免整句复制才算命中。"""
    s = point or ""
    hits: List[Dict[str, Any]] = []
    for sp in spans:
        frag = sp.get("text", "")
        if len(frag) < ANCHOR_WINDOW:
            ok = bool(frag) and frag in s
        else:
            ok = any(frag[i:i + ANCHOR_WINDOW] in s
                     for i in range(0, len(frag) - ANCHOR_WINDOW + 1))
        if ok:
            hits.append({"kind": sp["kind"], "text": frag, "source": sp["source"]})
    return hits


def raw_anchor(point: str, raw_text: str) -> Optional[Dict[str, Any]]:
    """原文级兜底锚点：问题点必须真的引用了「含失败词的原文句子」里的连续 4 字。

    只放宽「片段抽取是否覆盖到」，不放宽「是否原文有据」——模型凭空编造仍过不了；
    返回的可指认片段是原文整句，供 D2/D3 继续作证据依据。
    """
    s = (raw_text or "")[:EVIDENCE_TEXT_LIMIT]
    for m in _SENTENCE_RE.finditer(s):
        seg = m.group(0).strip()
        if len(seg) < ANCHOR_WINDOW:
            continue
        if not any(w in seg for w in _SENTENCE_FAILURE_WORDS):
            continue
        for i in range(0, len(seg) - ANCHOR_WINDOW + 1):
            if seg[i:i + ANCHOR_WINDOW] in (point or ""):
                return {"kind": "failure", "text": seg[:45], "source": "raw",
                        "anchor": seg[i:i + ANCHOR_WINDOW]}
    return None


def validate_point(point: str, spans: List[Dict[str, Any]],
                   raw_text: str = "") -> Dict[str, Any]:
    """**判定通道**：只用确定性规则，不复用生成结果自证、不含任何人工动作。"""
    checked = P.check_l1_point(point)
    hits = anchor_hits(point, spans)
    failure_anchors = [h for h in hits if h["kind"] in POINT_FAILURE_KINDS]
    if not failure_anchors and raw_text:
        hit = raw_anchor(point, raw_text)
        if hit:
            hits.append(hit)
            failure_anchors.append(hit)
    gaps: List[str] = list(checked["violations"])
    if not any(w in (point or "") for w in P.APPEAL_VERBS):
        gaps.append("P01 未写出客户/一线要办的事（诉求动词）")
    if not failure_anchors:
        gaps.append("P02 问题点未绑定可观察失败证据（无原文片段对应）")
    return {
        "ok": not gaps,
        "gaps": gaps,
        "anchors": hits,
        "failure_anchors": failure_anchors,
        "judge_channel": JUDGE_CHANNEL,
        "version": checked["version"],
    }


def build_point(ticket: Dict[str, Any],
                generator: Optional[Callable[[Dict[str, Any], List[Dict[str, Any]]], str]] = None
                ) -> Dict[str, Any]:
    """单张工单 → 逐单问题点结论。全程自动、只读、可复现。

    generator 是**唯一的语义生成插件**；为 None 表示通道不可用，此时绝不等人、
    绝不猜关键词，直接标 pending_auto_rerun 并写明缺口，供编排层通道恢复后自动补跑。
    """
    tno = str(ticket.get("ticket_no") or "")
    content = str(ticket.get("content") or "")
    solution = str(ticket.get("solution_history") or "")
    old = str(ticket.get("root_cause") or "")
    spans = extract_evidence_spans(content, solution)
    conclusion = detect_conclusion_record(old)

    base: Dict[str, Any] = {
        "ticket_no": tno,
        "policy_version": P.POLICY_VERSION,
        "point": "",
        "status": "",
        "gaps": [],
        "evidence": spans,
        "anchors": [],
        "old_record_conclusion": conclusion["is_conclusion"],
        "generator_channel": None,
        "judge_channel": JUDGE_CHANNEL,
    }

    # ① 证据不足（§3.2 E6）：原文无报错/状态值/缺失片段 → 自动拒识，不编造
    if not any(sp["kind"] in POINT_FAILURE_KINDS for sp in spans):
        base["status"] = P.UNCLASSIFIED_STATUS
        base["gaps"] = [P.DEGRADED_REASON_EVIDENCE]
        return base

    # ② 语义通道不可用（§1.3 失败自动退化）：不排队等人、不降级猜测
    if generator is None:
        base["status"] = P.DEGRADED_STATUS
        base["gaps"] = [P.DEGRADED_REASON_CHANNEL]
        if conclusion["is_conclusion"]:
            base["gaps"].append("存量逐单记录为结论式表述，须按 §2.5 自动重写")
        return base

    # ③ 生成 → 独立判定（分离）：生成结果必须重新过确定性闸门
    base["generator_channel"] = getattr(generator, "channel_name", "semantic-plugin")
    point = (generator(ticket, spans) or "").strip()
    if not point:
        # 区分「模型按 §1.3 判证据不足而显式返回空」与「批量回包漏返该单」：
        # 前者是自动拒识（不排队等人），后者是分析未完成，待通道恢复自动补跑。
        has = getattr(generator, "has", None)
        if callable(has) and has(tno):
            base["status"] = P.UNCLASSIFIED_STATUS
            base["gaps"] = [P.DEGRADED_REASON_EVIDENCE, "语义通道判定该单无可观察失败"]
            return base
        base["status"] = P.DEGRADED_STATUS
        base["gaps"] = [P.DEGRADED_REASON_CHANNEL, "语义通道漏返该单，待自动补跑"]
        return base
    judged = validate_point(point, spans, content + " " + solution)
    base["point"] = point
    base["anchors"] = judged["anchors"]
    base["gaps"] = judged["gaps"]
    base["status"] = "ok" if judged["ok"] else P.UNCLASSIFIED_STATUS
    if judged["ok"] and conclusion["is_conclusion"]:
        base["rewritten_from_conclusion"] = True
    return base


def scan_tickets(db: Session, limit: Optional[int] = None,
                 generator: Optional[Callable[..., str]] = None) -> Dict[str, Any]:
    """只读诊断：对现有工单逐单跑 L1 判定，输出合格率与待自动补跑清单。

    绝不写库；同输入两次调用结果一致（不含时间戳）。供 D5 编排与 CLI 复用。
    """
    sql = ("SELECT ticket_no, content, solution_history, root_cause "
           "FROM pmwb_complaint_ticket ORDER BY id")
    params: Dict[str, Any] = {}
    if limit:
        sql += " LIMIT :lim"
        params["lim"] = int(limit)
    rows = db.execute(text(sql), params).fetchall()

    stat = {"total": len(rows), "point_ok": 0, P.DEGRADED_STATUS: 0,
            P.UNCLASSIFIED_STATUS: 0, "conclusion_records": 0,
            "evidence_missing": 0, "pass_rate": 0.0, "samples": []}
    for r in rows:
        t = {"ticket_no": r[0], "content": r[1] or "", "solution_history": r[2] or "",
             "root_cause": r[3] or ""}
        res = build_point(t, generator=generator)
        if res["old_record_conclusion"]:
            stat["conclusion_records"] += 1
        if res["status"] == "ok":
            stat["point_ok"] += 1
        elif res["status"] == P.DEGRADED_STATUS:
            stat[P.DEGRADED_STATUS] += 1
        else:
            stat[P.UNCLASSIFIED_STATUS] += 1
            if P.DEGRADED_REASON_EVIDENCE in res["gaps"]:
                stat["evidence_missing"] += 1
        if len(stat["samples"]) < 5:
            stat["samples"].append({"ticket_no": res["ticket_no"], "status": res["status"],
                                    "gaps": res["gaps"][:3],
                                    "evidence_cnt": len(res["evidence"])})
    stat["pass_rate"] = round(stat["point_ok"] / stat["total"] * 100, 2) if stat["total"] else 0.0
    stat["policy_version"] = P.POLICY_VERSION
    return stat
