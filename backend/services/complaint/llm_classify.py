"""客诉工单 LLM 主导归类引擎（方案 v3.0，老大 2026-10-30 拍板）。

核心原则：
  - 每次分析都是大模型完成——输入 = 分类字典（4 类一级 × 二级场景）
    + 人工校正样例（few-shot）+ 工单投诉内容与往期处理过程全文；
  - 无关键词规则硬匹配（classify.py 规则引擎已废弃为兜底参考，不再调用）；
  - 输出结构化：一级/二级/置信度/判断依据（落 ai_confidence / ai_evidence，可追溯）；
  - 置信度 >= LLM_CONF_THRESHOLD → 自动归类（classify_by='ai'）；
    < 阈值 → 人工确认队列（classify_by='ai_low'，保留 LLM 最佳猜测供参考）；
  - LLM 不可用 → 工单保持待分析（category_l1=''），恢复后可重跑，绝不降级为规则匹配；
  - classify_by='manual'（人工校正）永不被覆盖，并作为 few-shot 样例回流提升准确率。

成本控制：增量分析（只分析未归类工单）、批量合并（LLM_BATCH_SIZE 条/次）、
单工单文本截断（LLM_TEXT_LIMIT）。
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.complaint import config as C
from services.llm_provider import call_best_available

logger = logging.getLogger(__name__)

UNCLASSIFIED = "未分类"

_SYSTEM_PROMPT = (
    "你是电信运营商政企/商客业务的客诉工单分析专家。你的任务是逐单分析投诉工单，"
    "基于工单的投诉内容和往期处理过程，从给定的分类字典中判断每个工单的问题性质（一级大类）"
    "和具体问题场景（二级场景）。\n"
    "判定要求：\n"
    "1. 必须从字典中给定的场景里选择，不得编造字典外的分类；\n"
    "2. 一级大类反映问题性质（系统问题=系统缺陷需研发修复 / 流程优化=流程或规则不合理需改造 / "
    "投诉咨询=咨询解释类可引导化解 / 数据问题=数据不一致或错误需批量修复）；\n"
    "3. 依据工单的实际处理过程判断，而不是只看投诉措辞；\n"
    "4. 给出 confidence（0~1）表示你对判断的把握，把握不足时宁低勿高；\n"
    "5. 给出 evidence：一句话摘录工单中最支持该判断的关键事实。\n"
    "输出要求：仅输出 JSON，不要输出任何其他文字。格式："
    '{"results": [{"no": "工单号", "l1": "一级大类", "l2": "二级场景或空串", '
    '"confidence": 0.0到1.0, "evidence": "判断依据"}]}'
)


# ── 字典与样例 ────────────────────────────────────────────────
def build_catalog(db: Session) -> Tuple[str, Dict[str, str], List[str]]:
    """生成分类字典清单文本。

    返回 (清单文本, {二级场景: 一级大类}, 全部一级大类列表)。
    """
    rows = db.execute(text(
        "SELECT level, parent_name, name FROM pmwb_complaint_category "
        "WHERE enabled = 1 ORDER BY level DESC, sort_order ASC"
    )).fetchall()
    l2_map: Dict[str, str] = {}
    l1_list: List[str] = []
    for level, parent, name in rows:
        if level == 1:
            l1_list.append(name)
        elif level == 2 and parent:
            l2_map[name] = parent
    lines = ["【一级大类】"] + [f"- {n}" for n in l1_list] + ["【二级场景（归属一级）】"]
    for l2, l1 in l2_map.items():
        lines.append(f"- {l2}（{l1}）")
    return "\n".join(lines), l2_map, l1_list


def load_few_shots(db: Session, per_group: int = C.LLM_FEWSHOT_PER_GROUP) -> List[Dict[str, str]]:
    """人工校正样例（few-shot）：classify_by='manual' 且已归类，按场景组取最近 N 条。"""
    if per_group <= 0:
        return []
    rows = db.execute(text(
        "SELECT ticket_no, content, solution_history, category_l1, category_l2 "
        "FROM pmwb_complaint_ticket "
        "WHERE classify_by = 'manual' AND category_l1 != '' AND category_l1 IS NOT NULL "
        "ORDER BY id DESC LIMIT 500"
    )).fetchall()
    picked: List[Dict[str, str]] = []
    seen: Dict[Tuple[str, str], int] = {}
    for no, content, solution, l1, l2 in rows:
        key = (l1 or "", l2 or "")
        if seen.get(key, 0) >= per_group:
            continue
        seen[key] = seen.get(key, 0) + 1
        picked.append({
            "no": no, "content": (content or "")[:C.LLM_TEXT_LIMIT],
            "solution": (solution or "")[:C.LLM_TEXT_LIMIT], "l1": l1, "l2": l2,
        })
    return picked


# ── Prompt 组装 ───────────────────────────────────────────────
def _fmt_shot(shot: Dict[str, str]) -> str:
    return (
        f'示例工单 {shot["no"]}：\n'
        f'  投诉内容：{shot["content"]}\n'
        f'  处理过程：{shot["solution"] or "（无）"}\n'
        f'  人工确认分类：一级={shot["l1"]}；二级={shot["l2"] or "空"}'
    )


def build_user_prompt(catalog: str, few_shots: List[Dict[str, str]],
                      tickets: Sequence[Dict[str, Any]]) -> str:
    parts = [catalog]
    if few_shots:
        parts.append("\n【人工确认样例（作为判定参考，注意与其保持口径一致）】")
        parts.extend(_fmt_shot(s) for s in few_shots)
    parts.append("\n【待分析工单】")
    for t in tickets:
        content = (t.get("content") or "")[:C.LLM_TEXT_LIMIT]
        solution = (t.get("solution") or "")[:C.LLM_TEXT_LIMIT]
        parts.append(
            f'工单 {t["ticket_no"]}：\n'
            f"  投诉内容：{content}\n"
            f"  处理过程：{solution or '（无）'}"
        )
    parts.append(
        f"\n请逐单输出分类结果（共 {len(tickets)} 单），"
        'JSON 格式：{"results": [{"no": "...", "l1": "...", "l2": "...", '
        '"confidence": 0.0, "evidence": "..."}]}'
    )
    return "\n".join(parts)


# ── 解析与校验 ────────────────────────────────────────────────
def _extract_json(raw: str) -> Optional[Dict[str, Any]]:
    """容错解析 LLM 返回：剥 ```json 包裹 / 截取首个平衡大括号段。"""
    if not raw:
        return None
    s = raw.strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s, flags=re.S).strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    start = s.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(s)):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(s[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def _validate_result(r: Dict[str, Any], l2_map: Dict[str, str],
                     l1_list: List[str]) -> Tuple[str, str, float]:
    """校验并修正单条 LLM 结果：l2 必须在字典内，l1 与字典归属对齐（防编造）。"""
    l1 = str(r.get("l1") or "").strip()
    l2 = str(r.get("l2") or "").strip()
    try:
        conf = float(r.get("confidence") or 0)
    except (TypeError, ValueError):
        conf = 0.0
    conf = max(0.0, min(1.0, conf))
    if l2 in l2_map:
        return l2_map[l2], l2, conf  # l1 以字典归属为准（零转译，防 LLM 漂移）
    if l1 in l1_list:
        return l1, "", conf
    return UNCLASSIFIED, "", 0.0


# ── 主流程 ────────────────────────────────────────────────────
def _pending_tickets(db: Session, force: bool, limit: Optional[int]) -> List[Dict[str, Any]]:
    """待分析工单：classify_by != 'manual' 且（force 或 category_l1 为空/未分类）。

    优先分析新工单（id 升序），limit 控制单次分析量。
    """
    cond = ("classify_by != 'manual'" if force
            else "classify_by != 'manual' AND (category_l1 IS NULL OR category_l1 = '' "
                 "OR category_l1 = '未分类')")
    lim = f" LIMIT {int(limit)}" if limit else ""
    rows = db.execute(text(
        "SELECT ticket_no, content, solution_history, category_l1, category_l2 "
        f"FROM pmwb_complaint_ticket WHERE {cond} ORDER BY id ASC{lim}"
    )).fetchall()
    return [{
        "ticket_no": r[0], "content": r[1], "solution": r[2],
        "category_l1": r[3], "category_l2": r[4],
    } for r in rows]


def run_llm_classify(db: Session, force: bool = False,
                     limit: Optional[int] = None) -> Dict[str, Any]:
    """LLM 主导归类主入口。返回统计与提示。

    - force=False 只分析待分析工单（l1 空/未分类）；
    - force=True 重分析全部非人工校正工单；
    - LLM 全部不可用时工单保持原状，返回 used_llm=False。
    """
    catalog, l2_map, l1_list = build_catalog(db)
    few_shots = load_few_shots(db)
    pending = _pending_tickets(db, force=force, limit=limit)
    if not pending:
        return {"scanned": 0, "updated": 0, "auto": 0, "low_conf": 0,
                "failed": 0, "used_llm": False, "notice": "没有待分析的工单"}

    idx = {t["ticket_no"]: t for t in pending}
    updated = auto = low = failed = 0
    notice = ""
    used_llm = False

    for i in range(0, len(pending), C.LLM_BATCH_SIZE):
        batch = pending[i:i + C.LLM_BATCH_SIZE]
        res = call_best_available(
            db, _SYSTEM_PROMPT,
            build_user_prompt(catalog, few_shots if not used_llm else [], batch),
            max_tokens=8000, timeout=300,
        )
        if not res.get("used_llm"):
            notice = res.get("notice") or "大模型不可用"
            break
        used_llm = True
        data = _extract_json(res.get("text") or "")
        items = (data or {}).get("results") or []
        by_no = {}
        for it in items:
            if isinstance(it, dict) and it.get("no"):
                by_no[str(it["no"])] = it

        for t in batch:
            no = t["ticket_no"]
            it = by_no.get(no)
            if not it:
                failed += 1
                continue
            l1, l2, conf = _validate_result(it, l2_map, l1_list)
            evidence = str(it.get("evidence") or "")[:500]
            if l1 == UNCLASSIFIED or conf < C.LLM_CONF_THRESHOLD:
                by = C.LLM_LOW_CONF_BY
                low += 1
            else:
                by = C.LLM_CLASSIFY_BY
                auto += 1
            db.execute(text(
                "UPDATE pmwb_complaint_ticket SET category_l1 = :l1, category_l2 = :l2, "
                "ai_confidence = :conf, ai_evidence = :ev, classify_by = :by "
                "WHERE ticket_no = :no AND classify_by != 'manual'"
            ), {"l1": l1, "l2": l2, "conf": conf, "ev": evidence, "by": by, "no": no})
            updated += 1

    db.commit()
    scanned = len(pending)
    return {
        "scanned": scanned, "updated": updated, "auto": auto, "low_conf": low,
        "failed": failed + max(0, scanned - updated - failed),
        "used_llm": used_llm,
        "notice": notice or ("LLM 归类完成" if used_llm else "大模型不可用，工单保持待分析"),
    }


def classify_status(db: Session) -> Dict[str, Any]:
    """归类状态统计（看板 AI 归类率 / 人工确认队列数据源）。"""
    total = db.execute(text(
        "SELECT COUNT(*) FROM pmwb_complaint_ticket")).scalar() or 0
    by = dict(db.execute(text(
        "SELECT classify_by, COUNT(*) FROM pmwb_complaint_ticket GROUP BY classify_by"
    )).fetchall())
    unclassified = db.execute(text(
        "SELECT COUNT(*) FROM pmwb_complaint_ticket "
        "WHERE classify_by != 'manual' AND (category_l1 IS NULL OR category_l1 = '')"
    )).scalar() or 0
    classified = total - unclassified
    return {
        "total": int(total),
        "ai": int(by.get(C.LLM_CLASSIFY_BY, 0)),
        "ai_low": int(by.get(C.LLM_LOW_CONF_BY, 0)),
        "manual": int(by.get(C.CLASSIFY_MANUAL_BY, 0)),
        "legacy_auto": int(by.get("auto", 0)),
        "unclassified": int(unclassified),
        "rate": round(classified / total * 100, 1) if total else 100.0,
    }
