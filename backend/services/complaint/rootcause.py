"""客诉工单 AI 根因归纳引擎（2026-11-03 客诉根因深化，老大拍板）。

为什么要有这个模块（问题复盘）：
  原方案让 LLM 从 30 个二级「现象场景」里做选择题，228 单平均 7.6 单/桶，
  最大桶 38 单混装 6 类不相关问题，AI 置信度 <0.85 占 71%——给定选项里就没有
  正确答案，模型只能勉强贴标签，真实信息（哪个账号、报什么错、哪一环断的）
  在选中那一刻就被丢掉了。而根因识别是后续批量投诉识别与解决方案制定的基础数据。

本模块的设计（与 llm_classify.py 的本质区别）：
  - **不选分类，而是写根因**：不再受字典约束，自由归纳「系统 + 环节 + 具体错误 + 影响」；
  - **质量门禁**：根因描述必须落到真实问题点（最小有效字数 + 泛词黑名单 + 必含具体标识），
    不合格退回重写一次，仍不合格落 rc_status='insufficient' 并记 rc_gap（信息缺口）。
    **不设人工队列**（2026-11-04 原则变更）：工单层分析必须全自动，人只在问题入账时确认；
  - **结构化标签**：fault_stage / fault_system / fault_type / own_party / fix_mode / repro
    六个受控枚举（唯一源 constants/complaint_rootcause.py），支撑环节漏斗、责任归属、
    「能不能一次消灭」等分析；
  - **置信度语义变了**：不再表示「分类对不对」，而是「工单信息是否足够判断根因」，
    信息不足（处理意见只有"已指导/已告知"）就应低置信，而不是硬猜；
  - 与 L0 现象分类（category_l1/l2）解耦：本模块不读不写 l1/l2，逐步替代其分析职能。

写入边界：本模块是 root_cause / fault_* / own_party / fix_mode / repro /
rc_status / rc_confidence / rc_evidence 的**唯一写入点**；
rootcause_no 的唯一写入点是 rootcause_lib.assign。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from constants import complaint_rootcause as RC
from services.complaint import config as C
from services.complaint.llm_classify import _extract_json
from services.llm_provider import call_best_available

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "你是电信运营商政企/商客业务客诉工单的根因分析专家。逐单做三件事：\n"
    "第一步 判定是否存在缺陷：系统缺陷、接口映射错误、数据不同步、配置缺失、"
    "规则不合理都算缺陷；仅是使用咨询、客户理解偏差、按规则解释的，判无缺陷。"
    "注意：处理意见只写「已指导/已告知/已解释」且没有任何技术动作的，通常是无缺陷。\n"
    "第二步 写根因（最关键）：必须回答「哪个系统 / 哪个环节 / 具体发生了什么错误 / 影响什么」，"
    "40~90 字。严禁空话套话（如「系统异常」「数据不一致」「需要核实」「操作咨询」「失败」「报错」）。"
    "必须带入工单中的具体事实：账号、订单号、协议号、报错原文、字段名、状态值、操作步骤。"
    "判断处置方式 fix_mode 时，看「这一类问题能否被一次脚本/一次改造消掉」，"
    "而不是看这单实际是怎么处理的——单笔转派不等于只能逐单处理。"
    "示例对比——\n"
    "  坏：客户电视激活失败，已协助处理。\n"
    "  好：电视账号 50051157045 在 HDC 激活校验返回「未开通」，机顶盒开通单未随宽带订单下发至"
    "电视平台，宽带侧已激活、电视侧无开通单。\n"
    "第三步 打结构化标签：从给定枚举中选，不得编造枚举外的值。\n"
    "置信度 confidence（0~1）表示「工单信息是否足够判断根因」，信息不足时宁低勿高，不要硬猜。"
    "锚点参考：工单内有明确报错原文/订单号/账号可追溯到具体环节 → 0.8 以上；"
    "只能从处理意见反推根因 → 0.6~0.75；处理意见只有「已指导/已告知」或内容残缺 → 0.5 以下。\n"
    "evidence 给出工单原文中支持该根因的具体片段（原样摘录，不要改写）。\n"
    "输出要求：仅输出 JSON，不要任何其他文字。格式："
    '{"results": [{"no": "工单号", "has_defect": true, "root_cause": "...", '
    '"fault_stage": "...", "fault_system": "...", "fault_type": "...", '
    '"own_party": "...", "fix_mode": "...", "repro": "yes|no|unknown", '
    '"confidence": 0.0, "evidence": "..."}]}'
)


# ── Prompt 组装 ───────────────────────────────────────────────
def _enum_block() -> str:
    return (
        "【受控枚举（必须从中选）】\n"
        f"故障环节 fault_stage：{'、'.join(RC.FAULT_STAGES)}\n"
        f"涉及系统 fault_system：{'、'.join(RC.FAULT_SYSTEMS)}\n"
        f"缺陷性质 fault_type：{'、'.join(RC.FAULT_TYPES)}\n"
        f"责任归属 own_party：{'、'.join(RC.OWN_PARTIES)}\n"
        f"处置方式 fix_mode：{'、'.join(RC.FIX_MODES)}\n"
        f"可复现性 repro：{'、'.join(RC.REPRO_VALUES)}（yes=同一路径可稳定重现）"
    )


def load_few_shots(db: Session) -> List[Dict[str, str]]:
    """few-shot：优先取根因库里已确认簇的代表单（口径统一），不足时补人工确认单。

    根因库上线后替代了原先「7 条人工分类样例」的贫瘠 few-shot。
    """
    picked: List[Dict[str, str]] = []
    try:
        rows = db.execute(text(
            "SELECT sample_tickets, title FROM pmwb_complaint_rootcause "
            "WHERE status = 'open' AND sample_tickets IS NOT NULL "
            "ORDER BY ticket_cnt DESC LIMIT 8"
        )).fetchall()
    except Exception:  # noqa: BLE001  根因库尚未建表时不阻断
        rows = []
    for samples, title in rows:
        try:
            nos = json.loads(samples or "[]")
        except (TypeError, ValueError):
            nos = []
        for no in nos[:C.RC_FEWSHOT_FROM_LIB]:
            if len(picked) >= C.RC_FEWSHOT_MAX:
                return picked
            t = db.execute(text(
                "SELECT ticket_no, content, solution_history, root_cause "
                "FROM pmwb_complaint_ticket WHERE ticket_no = :no"
            ), {"no": no}).first()
            if t:
                picked.append({"no": t[0], "content": (t[1] or "")[:800],
                               "solution": (t[2] or "")[:800],
                               "root_cause": t[3] or title or ""})
    # 不足则以人工确认根因为样例
    if len(picked) < C.RC_FEWSHOT_MAX:
        rows2 = db.execute(text(
            "SELECT ticket_no, content, solution_history, root_cause "
            "FROM pmwb_complaint_ticket WHERE rc_status = 'manual' AND root_cause != '' "
            "ORDER BY id DESC LIMIT :n"
        ), {"n": C.RC_FEWSHOT_MAX - len(picked)}).fetchall()
        for r in rows2:
            picked.append({"no": r[0], "content": (r[1] or "")[:800],
                           "solution": (r[2] or "")[:800], "root_cause": r[3] or ""})
    return picked


def _fmt_shot(s: Dict[str, str]) -> str:
    return (
        f'示例工单 {s["no"]}：\n'
        f'  投诉内容：{s["content"]}\n'
        f'  处理过程：{s["solution"] or "（无）"}\n'
        f'  根因写法：{s["root_cause"]}'
    )


def build_user_prompt(few_shots: Sequence[Dict[str, str]],
                      tickets: Sequence[Dict[str, Any]]) -> str:
    parts = [_enum_block()]
    if few_shots:
        parts.append("\n【已确认根因样例（口径参考，注意保持同类问题的描述颗粒度）】")
        parts.extend(_fmt_shot(s) for s in few_shots)
    parts.append("\n【待分析工单】")
    for t in tickets:
        content = (t.get("content") or "")[:C.RC_TEXT_LIMIT]
        solution = (t.get("solution") or "")[:C.RC_TEXT_LIMIT]
        parts.append(
            f'工单 {t["ticket_no"]}：\n'
            f"  投诉内容：{content}\n"
            f"  处理过程：{solution or '（无）'}"
        )
    parts.append(
        f"\n请逐单输出根因（共 {len(tickets)} 单），仅输出 JSON："
        '{"results": [{"no": "...", "has_defect": true, "root_cause": "...", '
        '"fault_stage": "...", "fault_system": "...", "fault_type": "...", '
        '"own_party": "...", "fix_mode": "...", "repro": "yes", '
        '"confidence": 0.8, "evidence": "..."}]}'
    )
    return "\n".join(parts)


# ── 质量门禁（核心：防再次"泛化"）────────────────────────────
def _effective_chars(s: str) -> int:
    """剔除泛词与标点后的有效字数（衡量「有没有说到点子上」）。"""
    t = s or ""
    for term in RC.GENERIC_TERMS:
        t = t.replace(term, "")
    t = re.sub(r"[\s，。、；：,.;:！？!?（）()\[\]【】\"'“”‘’/\\|—-]", "", t)
    return len(t)


def _has_concrete(cause: str) -> bool:
    """根因里是否带了具体标识（长数字/引号原文/系统-接口-字段-状态类实词）。

    比「必须出现 fault_system 名称」更合理：模型写「便民通」「HDC」比笼统写
    「第三方厂家系统」「电视平台」更精准，硬卡枚举名会把好根因判成不合格（实测踩坑）。
    """
    if re.search(r"\d{5,}", cause):
        return True
    if re.search(r"[「“\"'][^」”\"']{2,}[」”\"']", cause):
        return True
    return bool(re.search(
        r"(系统|平台|接口|字段|菜单|页面|模块|流程|规则|状态|报错|提示|单号|账号)", cause))


def quality_check(rc: Dict[str, Any]) -> List[str]:
    """返回不合格原因列表（空列表 = 过门禁）。

    门禁项（对应老大「不能太泛、要细化到真实问题描述」的硬要求）：
      G1 总字数够长（>= RC_MIN_TOTAL_CHARS）
      G2 剔泛词后有效字数够（>= RC_MIN_EFFECTIVE_CHARS）——防「系统异常需核实」式空话
      G3 必须带具体标识（长数字/引号原文/系统-接口-字段类实词），否则仍是泛泛而谈
      G4 五个受控枚举必须落在枚举内（normalize 后非空）
      G5 has_defect=false 时 fault_type 必须是「无缺陷」，反之不得为「无缺陷」
    """
    reasons: List[str] = []
    cause = (rc.get("root_cause") or "").strip()
    if len(cause) < RC.RC_MIN_TOTAL_CHARS:
        reasons.append(f"G1 根因过短（{len(cause)}字）")
    if _effective_chars(cause) < RC.RC_MIN_EFFECTIVE_CHARS:
        reasons.append("G2 根因过于笼统（泛词占比过高）")
    if not _has_concrete(cause):
        reasons.append("G3 根因缺少具体标识（无单号/账号/报错原文/字段名）")
    for key, label in (("fault_stage", "故障环节"), ("fault_system", "涉及系统"),
                       ("fault_type", "缺陷性质"), ("own_party", "责任归属"),
                       ("fix_mode", "处置方式")):
        if not rc.get(key):
            reasons.append(f"G4 {label}未落枚举")
    if rc.get("has_defect") and rc.get("fault_type") == "无缺陷":
        reasons.append("G5 有缺陷却标「无缺陷」")
    if (not rc.get("has_defect")) and rc.get("fault_type") not in ("无缺陷", None, ""):
        reasons.append("G5 无缺陷却标了缺陷性质")
    return reasons


def _gap_text(reasons: List[str], rc: Dict[str, Any]) -> str:
    """生成信息缺口说明（存 rc_gap），让人一眼看出这条根因为什么不够硬。

    只描述缺口，不写结论——避免与 root_cause 抢口径。
    """
    parts = [r.split(" ", 1)[-1] for r in reasons] if reasons else []
    if not parts:
        parts.append(f"模型置信不足（{rc.get('confidence') or 0:.2f}）")
    return ("信息不足：" + "；".join(parts[:3]))[:255]


def _normalize(item: Dict[str, Any]) -> Dict[str, Any]:
    """把 LLM 单条输出对齐到受控枚举（防编造，越界即置空由门禁拦截）。"""
    try:
        conf = float(item.get("confidence") or 0)
    except (TypeError, ValueError):
        conf = 0.0
    conf = max(0.0, min(1.0, conf))
    has_defect = item.get("has_defect")
    if isinstance(has_defect, str):
        has_defect = has_defect.strip().lower() in ("true", "1", "yes", "是")
    repro = RC.normalize_choice(str(item.get("repro") or ""), RC.REPRO_VALUES)
    return {
        "has_defect": bool(has_defect),
        "root_cause": str(item.get("root_cause") or "").strip()[:500],
        "fault_stage": RC.normalize_choice(str(item.get("fault_stage") or ""), RC.FAULT_STAGES),
        "fault_system": RC.normalize_choice(str(item.get("fault_system") or ""), RC.FAULT_SYSTEMS),
        "fault_type": RC.normalize_choice(str(item.get("fault_type") or ""), RC.FAULT_TYPES),
        "own_party": RC.normalize_choice(str(item.get("own_party") or ""), RC.OWN_PARTIES),
        "fix_mode": RC.normalize_choice(str(item.get("fix_mode") or ""), RC.FIX_MODES),
        "repro": repro or "unknown",
        "confidence": conf,
        "evidence": str(item.get("evidence") or "").strip()[:500],
    }


# ── 写库 ─────────────────────────────────────────────────────
def _save(db: Session, ticket_no: str, rc: Dict[str, Any], status: str,
          gap: str = "") -> None:
    db.execute(text(
        "UPDATE pmwb_complaint_ticket SET "
        "root_cause = :rc, fault_stage = :fs, fault_system = :fy, fault_type = :ft, "
        "own_party = :op, fix_mode = :fm, repro = :rp, rc_status = :st, "
        "rc_confidence = :cf, rc_evidence = :ev, rc_gap = :gp "
        "WHERE ticket_no = :no AND (rc_status != 'manual' OR rc_status IS NULL)"
    ), {"rc": rc["root_cause"], "fs": rc["fault_stage"], "fy": rc["fault_system"],
        "ft": rc["fault_type"], "op": rc["own_party"], "fm": rc["fix_mode"],
        "rp": rc["repro"], "st": status, "cf": rc["confidence"],
        "ev": rc["evidence"], "gp": gap or None, "no": ticket_no})


def _rewrite_batch(db: Session, tasks: List[Tuple[Dict[str, Any], List[str], Dict[str, Any]]]
                   ) -> Dict[str, Dict[str, Any]]:
    """未过门禁的单批量重写一次（把不合格原因回灌给模型）。

    性能教训（2026-11-03 实测）：逐条重写会让调用次数翻 3 倍、存量重跑耗时爆炸，
    故同批不合格单合并成一次调用（上限 RC_REWRITE_BATCH 条）。
    """
    if not tasks:
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for i in range(0, len(tasks), C.RC_REWRITE_BATCH):
        chunk = tasks[i:i + C.RC_REWRITE_BATCH]
        tickets = [t[0] for t in chunk]
        base = build_user_prompt([], tickets)
        notes = ["\n【上一版不合格，必须逐单重写】"]
        for t, reasons, prev in chunk:
            notes.append(
                f'工单 {t["ticket_no"]} 上一版根因：{prev.get("root_cause") or "（空）"}'
                f'；不合格原因：{"；".join(reasons) or "置信不足"}'
            )
        notes.append(
            "要求：必须写清「哪个系统 + 哪个环节 + 具体报错/字段/状态 + 影响什么」，"
            "带入工单里的账号/订单号/报错原文，不要使用「系统异常」「数据不一致」"
            "「需要核实」「操作咨询」这类空话。仅输出 JSON（格式同前）。"
        )
        res = call_best_available(
            db, _SYSTEM_PROMPT, base + "\n".join(notes),
            max_tokens=6000, timeout=300,
        )
        if not res.get("used_llm"):
            continue
        data = _extract_json(res.get("text") or "") or {}
        for it in (data.get("results") or []):
            if isinstance(it, dict) and it.get("no"):
                out[str(it["no"]).strip()] = _normalize(it)
    return out


# ── 主流程 ────────────────────────────────────────────────────
def _pending_tickets(db: Session, force: bool, limit: Optional[int]) -> List[Dict[str, Any]]:
    # 注意 SQL 三值逻辑：`rc_status != 'manual'` 对 NULL 求值为 NULL 而非 TRUE，
    # 必须先显式判 NULL，否则新单（rc_status 为 NULL）永远扫不出来（2026-11-03 实测踩坑）。
    cond = ("(rc_status IS NULL OR rc_status != 'manual')" if force
            else "(rc_status IS NULL OR rc_status = '')")
    lim = f" LIMIT {int(limit)}" if limit else ""
    rows = db.execute(text(
        "SELECT ticket_no, content, solution_history FROM pmwb_complaint_ticket "
        f"WHERE {cond} ORDER BY id ASC{lim}"
    )).fetchall()
    return [{"ticket_no": r[0], "content": r[1], "solution": r[2]} for r in rows]


def run_rootcause(db: Session, force: bool = False,
                  limit: Optional[int] = None) -> Dict[str, Any]:
    """根因归纳主入口。

    - force=False 只分析待分析工单（rc_status 空）；
    - force=True 重跑全部非人工确认工单；
    - LLM 不可用时工单保持待分析，绝不降级为规则拼装。
    """
    pending = _pending_tickets(db, force=force, limit=limit)
    if not pending:
        return {"scanned": 0, "saved": 0, "ok": 0, "low": 0, "rewritten": 0,
                "failed": 0, "used_llm": False, "notice": "没有待分析的工单"}

    few_shots = load_few_shots(db)
    saved = ok = low = rewritten = failed = 0
    used_llm = False
    notice = ""
    to_rewrite: List[Tuple[Dict[str, Any], List[str], Dict[str, Any]]] = []

    for i in range(0, len(pending), C.RC_BATCH_SIZE):
        batch = pending[i:i + C.RC_BATCH_SIZE]
        res = call_best_available(
            db, _SYSTEM_PROMPT,
            build_user_prompt(few_shots if not used_llm else [], batch),
            max_tokens=8000, timeout=300,
        )
        if not res.get("used_llm"):
            notice = res.get("notice") or "大模型不可用"
            break
        used_llm = True
        data = _extract_json(res.get("text") or "") or {}
        by_no = {}
        for it in (data.get("results") or []):
            if isinstance(it, dict) and it.get("no"):
                by_no[str(it["no"]).strip()] = it

        for t in batch:
            no = t["ticket_no"]
            item = by_no.get(no)
            if not item:
                failed += 1
                continue
            rc = _normalize(item)
            reasons = quality_check(rc)
            if not reasons and rc["confidence"] >= C.RC_CONF_THRESHOLD:
                _save(db, no, rc, RC.RC_STATUS_AI)
                saved += 1
                ok += 1
                continue
            to_rewrite.append((t, reasons, rc))

        # 批内不合格单合并重写一次（不逐条调，防调用次数爆炸）
        if to_rewrite and C.RC_REWRITE_ONCE:
            rewritten_map = _rewrite_batch(db, to_rewrite)
            for t, reasons, prev in to_rewrite:
                no = t["ticket_no"]
                rc = rewritten_map.get(no) or prev
                if no in rewritten_map:
                    rewritten += 1
                    reasons = quality_check(rc)
                passed = not reasons and rc["confidence"] >= C.RC_CONF_THRESHOLD
                _save(db, no, rc,
                      RC.RC_STATUS_AI if passed else RC.RC_STATUS_INSUFFICIENT,
                      gap="" if passed else _gap_text(reasons, rc))
                saved += 1
                if passed:
                    ok += 1
                else:
                    low += 1
                    logger.info("根因信息不足 %s：%s（置信 %.2f）", no,
                                "；".join(reasons) or "置信不足", rc["confidence"])
            to_rewrite.clear()
        else:
            for t, reasons, rc in to_rewrite:
                _save(db, t["ticket_no"], rc, RC.RC_STATUS_INSUFFICIENT,
                      gap=_gap_text(reasons, rc))
                saved += 1
                low += 1
            to_rewrite.clear()

    db.commit()
    return {
        "scanned": len(pending), "saved": saved, "ok": ok, "low": low,
        "rewritten": rewritten, "failed": failed, "used_llm": used_llm,
        "notice": notice or ("根因归纳完成" if used_llm else "大模型不可用，工单保持待分析"),
    }


def rejudge(db: Session) -> Dict[str, Any]:
    """按当前门禁与阈值重判存量「信息不足」单（零 LLM 成本）。

    用途：调过质量门禁或置信度阈值后，不必重跑模型，直接按新口径重判。
    仍不合格者刷新缺口说明，状态保持 insufficient。
    """
    rows = db.execute(text(
        "SELECT ticket_no, root_cause, fault_stage, fault_system, fault_type, "
        "own_party, fix_mode, rc_confidence FROM pmwb_complaint_ticket "
        "WHERE rc_status = :st"
    ), {"st": RC.RC_STATUS_INSUFFICIENT}).fetchall()
    promoted = 0
    for r in rows:
        rc = {
            "root_cause": r[1] or "", "fault_stage": r[2] or "", "fault_system": r[3] or "",
            "fault_type": r[4] or "", "own_party": r[5] or "", "fix_mode": r[6] or "",
            "confidence": float(r[7] or 0),
            "has_defect": (r[4] or "") not in ("", "无缺陷"),
        }
        reasons = quality_check(rc)
        if not reasons and rc["confidence"] >= C.RC_CONF_THRESHOLD:
            db.execute(text(
                "UPDATE pmwb_complaint_ticket SET rc_status = :st, rc_gap = NULL "
                "WHERE ticket_no = :no"
            ), {"st": RC.RC_STATUS_AI, "no": r[0]})
            promoted += 1
        else:
            db.execute(text(
                "UPDATE pmwb_complaint_ticket SET rc_gap = :gp WHERE ticket_no = :no"
            ), {"gp": _gap_text(reasons, rc), "no": r[0]})
    db.commit()
    return {"scanned": len(rows), "promoted": promoted, "remained": len(rows) - promoted}


def update_manual(db: Session, ticket_no: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """人工校正单条根因（置 rc_status='manual'，此后重跑永不覆盖）。

    字段写入口径唯一在本模块：根因描述同样过质量门禁（软校验：不通过仅提示，不阻断人工）。
    """
    row = db.execute(text(
        "SELECT id FROM pmwb_complaint_ticket WHERE ticket_no = :no"), {"no": ticket_no}).first()
    if not row:
        return {"ok": False, "message": "工单不存在"}
    rc = {
        "root_cause": (payload.get("root_cause") or "").strip()[:500],
        "fault_stage": RC.normalize_choice(str(payload.get("fault_stage") or ""), RC.FAULT_STAGES),
        "fault_system": RC.normalize_choice(str(payload.get("fault_system") or ""), RC.FAULT_SYSTEMS),
        "fault_type": RC.normalize_choice(str(payload.get("fault_type") or ""), RC.FAULT_TYPES),
        "own_party": RC.normalize_choice(str(payload.get("own_party") or ""), RC.OWN_PARTIES),
        "fix_mode": RC.normalize_choice(str(payload.get("fix_mode") or ""), RC.FIX_MODES),
        "repro": RC.normalize_choice(str(payload.get("repro") or ""), RC.REPRO_VALUES) or "unknown",
        "confidence": 1.0,
        "evidence": (payload.get("evidence") or "").strip()[:500],
    }
    has_defect = payload.get("has_defect")
    if isinstance(has_defect, str):
        has_defect = has_defect.strip().lower() in ("true", "1", "yes", "是")
    rc["has_defect"] = (rc["fault_type"] not in ("", "无缺陷")) if has_defect is None else bool(has_defect)
    db.execute(text(
        "UPDATE pmwb_complaint_ticket SET root_cause = :rc, fault_stage = :fs, "
        "fault_system = :fy, fault_type = :ft, own_party = :op, fix_mode = :fm, "
        "repro = :rp, rc_status = 'manual', rc_confidence = 1.0, rc_evidence = :ev "
        "WHERE ticket_no = :no"
    ), {"rc": rc["root_cause"], "fs": rc["fault_stage"], "fy": rc["fault_system"],
        "ft": rc["fault_type"], "op": rc["own_party"], "fm": rc["fix_mode"],
        "rp": rc["repro"], "ev": rc["evidence"], "no": ticket_no})
    db.commit()
    logger.info("根因人工校正 %s", ticket_no)
    return {"ok": True, "root_cause": rc["root_cause"],
            "quality_warnings": quality_check(rc)}


def rootcause_status(db: Session) -> Dict[str, Any]:
    """根因归纳状态统计（看板数据源）。

    口径说明（必须分开，否则误导）：
      - coverage  根因覆盖率 = 有根因的单 / 总数（含信息不足）
      - quality   高质量率 = rc_status='ai' / 总数（真正可支撑分析的根因）
      - need_analyze 待分析 / insufficient 信息不足（AI 已尽力，不需人工介入）
    """
    total = db.execute(text(
        "SELECT COUNT(*) FROM pmwb_complaint_ticket")).scalar() or 0
    rows = db.execute(text(
        "SELECT COALESCE(rc_status,'') s, COUNT(*) FROM pmwb_complaint_ticket "
        "GROUP BY COALESCE(rc_status,'')")).fetchall()
    by = {r[0]: int(r[1]) for r in rows}
    filled = db.execute(text(
        "SELECT COUNT(*) FROM pmwb_complaint_ticket "
        "WHERE root_cause IS NOT NULL AND root_cause != ''")).scalar() or 0
    ai = by.get(RC.RC_STATUS_AI, 0)
    low = by.get(RC.RC_STATUS_INSUFFICIENT, 0)
    manual = by.get(RC.RC_STATUS_MANUAL, 0)
    pending = max(0, total - ai - low - manual)
    lib = {}
    try:
        lib = dict(db.execute(text(
            "SELECT status, COUNT(*) FROM pmwb_complaint_rootcause GROUP BY status"
        )).fetchall())
    except Exception:  # noqa: BLE001
        pass
    return {
        "total": int(total),
        "ai": ai, "low": low, "manual": manual, "need_analyze": pending,
        "filled": int(filled),
        "coverage": round(filled / total * 100, 1) if total else 0.0,
        "quality": round((ai + manual) / total * 100, 1) if total else 0.0,
        "rootcause_lib": {k: int(v) for k, v in lib.items()},
    }
