"""AI 问答：基于项目数据库 + Obsidian 笔记的本地智能检索问答。

设计要点（A 档 + B 档）：
- A 档（检索质量）：
  * 相关性打分：DB 命中按「命中词长权重 × 关键字段加倍」计分，跨 7 张表统一按分排序取 TopN，
    不再按时间取最新（旧实现的最大质量坑）。
  * Obsidian 保底：按命中密度打分，优先「商客业务」知识文件夹，保证知识笔记进入上下文的份额。
  * 片段优选：用滑动窗口按命中密度抽取最佳段落（放宽到 700 字），而非首个命中词周围 400 字。
  * 领域同义词/缩写归一：内置商客领域 alias，扩展检索词（一网通↔融合开通、FTTO↔光纤到办公室…）。
- B 档（LLM 增强，复用「大模型管理」既有 LLM，零新依赖）：
  * 查询改写：调用统一 LLM 把自然语言问题改写为精确检索词与同义短语（JSON），提升召回与同义/缩写匹配。
  * 两阶段问答：LLM 改写扩展检索词 → 多路召回（DB+Obsidian 打分）→ 大模型基于编号材料作答（自重排）。
  * 大模型不可用时，自动跳过改写、退回纯词法召回，不影响问答可用性。
- 不编造：提示词要求仅依据检索材料作答并引用 [编号]，材料不足时明说「未找到」。
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session

from core.config import settings
from db.models import (
    PmwbDevTicket,
    PmwbKnowledgeItem,
    PmwbMeeting,
    PmwbOperationIssue,
    PmwbRequirementEvaluation,
    PmwbUserStory,
    SentEmail,
)
from services.llm_provider import call_best_available

logger = logging.getLogger(__name__)

# 检索边界（单次问答）
VAULT_MAX_SCAN = 500        # 最多扫描的 Obsidian 文件数
VAULT_MAX_SNIPPETS = 8      # 最多采纳的 Obsidian 片段数
DB_CANDIDATES_PER_TABLE = 25  # 每张表召回候选数（用于打分后取 TopN）
TOP_K = 16                  # 最终进入上下文的来源数上限
GUARANTEE_OB = 2            # 至少保证的 Obsidian 来源数
CTX_TOTAL_MAX = 13000       # 上下文总字符上限
SNIPPET_MAX = 900           # 单条片段最大字符数

# 优先扫描的业务知识文件夹（商客业务主笔记所在）
PRIORITY_OB_FOLDER = "01-业务知识/商客业务"

SYSTEM_PROMPT = (
    "你是一名产品经理个人工作台的「智能问答助手」，基于下方从「项目数据库」与「Obsidian 知识笔记」"
    "检索到的材料（已按 [编号] 标注）回答用户问题。\n\n"
    "【回答要求】\n"
    "1. 仅依据上述编号材料作答；若材料不足以回答，明确说明「在项目数据中未找到相关信息」，不得编造或臆测。\n"
    "2. 关键结论用 [编号] 标注来源，可综合多个来源；提及需求/工单/会议时尽量带上编号或标题。\n"
    "3. 以产品经理视角，结构化、分点、语言简洁；必要时给出下一步建议或待确认事项。\n"
    "4. 若不同材料之间存在不一致或明显缺失，请指出，并说明需要补充的信息。"
)

# 商客领域同义词 / 缩写归一（用于扩展检索词，提升召回与同义匹配）
DOMAIN_SYNONYMS: List[List[str]] = [
    ["一网通", "融合开通", "融合接入", "一网通宽带", "商客融合"],
    ["FTTO", "光纤到办公室", "光纤到桌面", "FTTB"],
    ["商客", "商业客户", "集团商客", "商客市场"],
    ["交付", "开通", "受理", "开通交付", "交付一次成功率"],
    ["安防", "安全", "商客安防"],
    ["专线", "数据专线", "互联网专线", "专线卫士"],
    ["知识库", "知识图谱", "笔记", "知识笔记", "知识条目"],
    ["需求", "需求台账", "需求分析", "需求说明书"],
    ["工单", "开发工单", "开发单", "运维单"],
    ["运营", "生产运营", "业务运营", "运营问题"],
    ["会议", "纪要", "会议纪要"],
    ["评估", "团队评估", "SA评估", "技术评估"],
    ["SaaS", "saas", "SaaS业务", "软件即服务"],
    ["宽带电视", "IPTV", "电视"],
    ["电子协议", "电子合同", "协议"],
    ["订单中心", "订单", "订单系统"],
    ["政企工作台", "政企工作台系统", "工作台"],
]


# ---------------------------------------------------------------------------
# 分词与匹配
# ---------------------------------------------------------------------------

def _sanitize_token(t: str) -> str:
    return (t or "").strip().replace("%", "").replace("_", "")


def tokenize(question: str) -> List[str]:
    """把问题切成检索词：整句（短）、空白/标点切分片段、CJK 2/3 元片段。"""
    q = (question or "").strip()
    raw: List[str] = []
    if 0 < len(q) <= 15:
        raw.append(q)
    for part in re.split(r"[\s,，。、；;：:！!？?（）()]+", q):
        part = part.strip()
        if len(part) >= 2:
            raw.append(part)
    for run in re.findall(r"[一-鿿]+", q):
        n = len(run)
        if n <= 4:
            raw.append(run)
        else:
            for g in (2, 3):
                for i in range(n - g + 1):
                    raw.append(run[i : i + g])
    seen = set()
    out: List[str] = []
    for t in raw:
        t = _sanitize_token(t)
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def expand_synonyms(tokens: List[str]) -> List[str]:
    """基于领域同义词表扩展检索词（命中某组的任一成员则带入整组）。"""
    out = list(tokens)
    ts = set(tokens)
    for group in DOMAIN_SYNONYMS:
        if any(g in ts for g in group):
            for g in group:
                if g not in ts:
                    ts.add(g)
                    out.append(g)
    # 限制规模，避免条件爆炸
    return out[:50]


# ---------------------------------------------------------------------------
# 打分工具
# ---------------------------------------------------------------------------

def _score_text(text: str, tokens: List[str], weights: Optional[Dict[str, float]] = None) -> float:
    """文本命中打分：对每个命中词按 词长^0.5 × 出现次数(封顶3) × 词权重 累加。"""
    weights = weights or {}
    score = 0.0
    for t in tokens:
        if len(t) < 2:
            continue
        cnt = text.count(t)
        if cnt > 0:
            w = weights.get(t, 1.0)
            score += (len(t) ** 0.5) * min(cnt, 3) * w
    return score


def _score_texts(texts: List[Tuple[str, bool]], tokens: List[str], weights: Optional[Dict[str, float]] = None) -> float:
    """多字段文本打分：命中词若在关键字段则加倍，每个词至多计一次；扩展词权重更低。"""
    weights = weights or {}
    score = 0.0
    matched: set = set()
    for t in tokens:
        if len(t) < 2:
            continue
        wt = weights.get(t, 1.0)
        for txt, is_key in texts:
            if t in txt and t not in matched:
                score += (len(t) ** 0.5) * (2.0 if is_key else 1.0) * wt
                matched.add(t)
                break
    return score


def _normalize(vals: List[float]) -> List[float]:
    if not vals:
        return []
    m = max(vals)
    if m <= 0:
        return [0.0] * len(vals)
    return [v / m for v in vals]


def _clip(s: str, n: int = 600) -> str:
    s = (s or "").replace("\r", "").replace("\n", " ").strip()
    return s[:n] + ("…" if len(s) > n else "")


def _json_field(raw) -> str:
    if not raw:
        return ""
    if isinstance(raw, (list, dict)):
        try:
            return _clip("；".join(map(str, raw)) if isinstance(raw, list) else str(raw), 300)
        except Exception:  # noqa: BLE001
            return ""
    return _clip(str(raw), 300)


def _first_heading(text: str) -> str:
    for line in (text or "").splitlines():
        m = re.match(r"^#\s+(.+)$", line.strip())
        if m:
            return m.group(1).strip()
    return ""


def _best_snippet(text: str, tokens: List[str], max_chars: int = SNIPPET_MAX) -> str:
    """滑动窗口按命中密度抽取最佳段落。"""
    text = (text or "").replace("\r", "")
    if not text:
        return ""
    toks = [t for t in tokens if len(t) >= 2]
    if not toks:
        return _clip(text, max_chars)
    best_score = -1.0
    best: Optional[Tuple[int, int]] = None
    step = max(80, max_chars // 2)
    for start in range(0, max(len(text), max_chars), step):
        end = min(len(text), start + max_chars)
        win = text[start:end]
        sc = sum(win.count(t) * (len(t) ** 0.5) for t in toks)
        if sc > best_score:
            best_score = sc
            best = (start, end)
    if best is None or best_score <= 0:
        return _fallback_snippet(text, toks, max_chars)
    s, e = best
    snip = text[s:e].strip()
    if s > 0:
        snip = "…" + snip
    if e < len(text):
        snip = snip + "…"
    return snip


def _fallback_snippet(text: str, tokens: List[str], max_chars: int = SNIPPET_MAX) -> str:
    pos = -1
    for t in tokens:
        idx = text.find(t)
        if idx >= 0 and (pos < 0 or idx < pos):
            pos = idx
    if pos < 0:
        return _clip(text, max_chars)
    start = max(0, pos - 80)
    end = min(len(text), pos + max_chars - 80)
    snip = text[start:end].strip()
    if start > 0:
        snip = "…" + snip
    if end < len(text):
        snip = snip + "…"
    return snip


# ---------------------------------------------------------------------------
# 数据库检索（相关性打分 + 跨表统一排序）
# ---------------------------------------------------------------------------

_DB_TABLES = [
    {
        "name": "需求",
        "model": SentEmail,
        "cols": [
            SentEmail.req_id, SentEmail.req_name, SentEmail.system_name,
            SentEmail.proposer, SentEmail.background, SentEmail.description,
            SentEmail.clarification,
        ],
        "key_cols": {SentEmail.req_name, SentEmail.system_name},
        "title": lambda r: r.req_name or r.req_id or "需求",
        "ref": lambda r: r.req_id or "",
    },
    {
        "name": "用户故事",
        "model": PmwbUserStory,
        "cols": [
            PmwbUserStory.req_id, PmwbUserStory.title, PmwbUserStory.desc,
            PmwbUserStory.scene, PmwbUserStory.acceptance, PmwbUserStory.rules,
        ],
        "key_cols": {PmwbUserStory.title},
        "title": lambda r: r.title or f"US{r.seq}",
        "ref": lambda r: r.req_id or "",
    },
    {
        "name": "团队评估",
        "model": PmwbRequirementEvaluation,
        "cols": [
            PmwbRequirementEvaluation.req_id, PmwbRequirementEvaluation.system_name,
            PmwbRequirementEvaluation.sa_name, PmwbRequirementEvaluation.opinion,
            PmwbRequirementEvaluation.dev_ticket_no,
        ],
        "key_cols": {PmwbRequirementEvaluation.system_name},
        "title": lambda r: f"{r.system_name or ''} 评估",
        "ref": lambda r: r.req_id or "",
    },
    {
        "name": "开发工单",
        "model": PmwbDevTicket,
        "cols": [
            PmwbDevTicket.ticket_no, PmwbDevTicket.req_id, PmwbDevTicket.system_name,
            PmwbDevTicket.dev_team, PmwbDevTicket.developer, PmwbDevTicket.description,
            PmwbDevTicket.risk_note,
        ],
        "key_cols": {PmwbDevTicket.ticket_no, PmwbDevTicket.system_name},
        "title": lambda r: r.ticket_no or "开发工单",
        "ref": lambda r: r.ticket_no or "",
    },
    {
        "name": "运营问题",
        "model": PmwbOperationIssue,
        "cols": [
            PmwbOperationIssue.issue_no, PmwbOperationIssue.title,
            PmwbOperationIssue.situation_desc, PmwbOperationIssue.root_cause,
            PmwbOperationIssue.solution, PmwbOperationIssue.related_req_id,
            PmwbOperationIssue.related_ticket_no, PmwbOperationIssue.related_system,
        ],
        "key_cols": {PmwbOperationIssue.title},
        "title": lambda r: r.title or r.issue_no or "运营问题",
        "ref": lambda r: r.issue_no or "",
    },
    {
        "name": "会议",
        "model": PmwbMeeting,
        "cols": [
            PmwbMeeting.meeting_id, PmwbMeeting.title, PmwbMeeting.summary,
            PmwbMeeting.host, PmwbMeeting.related_req_id, PmwbMeeting.related_ticket_no,
        ],
        "key_cols": {PmwbMeeting.title},
        "title": lambda r: r.title or r.meeting_id or "会议",
        "ref": lambda r: r.meeting_id or "",
    },
    {
        "name": "知识库",
        "model": PmwbKnowledgeItem,
        "cols": [
            PmwbKnowledgeItem.item_id, PmwbKnowledgeItem.title,
            PmwbKnowledgeItem.tags, PmwbKnowledgeItem.summary,
        ],
        "key_cols": {PmwbKnowledgeItem.title},
        "title": lambda r: r.title or r.item_id or "知识条目",
        "ref": lambda r: r.obsidian_path or r.item_id or "",
    },
]


def _row_full_text(r, cfg) -> str:
    parts: List[str] = []
    for c in cfg["cols"]:
        v = getattr(r, c.name, None)
        if isinstance(v, (list, dict)):
            v = _json_field(v)
        elif v is not None:
            v = str(v)
        else:
            v = ""
        if v:
            parts.append(v)
    return " ".join(parts)


def _search_db_scored(db: Session, tokens: List[str], weights: Optional[Dict[str, float]] = None) -> List[Dict[str, Any]]:
    """跨项目数据库多表相关性召回，返回带 score 的来源列表。"""
    db_tokens = [t for t in tokens if len(t) >= 2]
    if not db_tokens:
        db_tokens = tokens
    out: List[Dict[str, Any]] = []
    for cfg in _DB_TABLES:
        cols = cfg["cols"]
        key_cols = cfg.get("key_cols", set())
        conds = []
        for c in cols:
            for t in db_tokens:
                conds.append(c.like(f"%{t}%"))
        if not conds:
            continue
        try:
            rows = db.query(cfg["model"]).filter(or_(*conds)).limit(DB_CANDIDATES_PER_TABLE).all()
        except Exception:  # noqa: BLE001
            continue
        for r in rows:
            try:
                texts = []
                for c in cols:
                    v = getattr(r, c.name, None)
                    if isinstance(v, (list, dict)):
                        v = _json_field(v)
                    elif v is not None:
                        v = str(v)
                    else:
                        v = ""
                    texts.append((v, c in key_cols))
                score = _score_texts(texts, db_tokens, weights)
                if score <= 0:
                    continue
                full = _row_full_text(r, cfg)
                out.append({
                    "type": "db",
                    "kind": cfg["name"],
                    "title": cfg["title"](r),
                    "ref": cfg["ref"](r),
                    "snippet": _best_snippet(full, db_tokens),
                    "score": score,
                })
            except Exception:  # noqa: BLE001
                continue
    return out


# ---------------------------------------------------------------------------
# Obsidian 检索（密度打分 + 业务文件夹优先 + 保底）
# ---------------------------------------------------------------------------

def _search_obsidian_scored(tokens: List[str], weights: Optional[Dict[str, float]] = None) -> List[Dict[str, Any]]:
    """扫描 Obsidian vault 的 .md 笔记，按命中密度打分，优先商客业务文件夹。"""
    vault = Path(settings.OBSIDIAN_VAULT_PATH)
    if not vault.exists():
        return []
    results: List[Dict[str, Any]] = []
    scanned = 0
    for root, dirs, files in os.walk(vault):
        dirs[:] = [
            d for d in dirs
            if not d.startswith(".") and d.lower() not in ("attachment", "attachments")
        ]
        for fn in files:
            if not fn.lower().endswith(".md"):
                continue
            scanned += 1
            if scanned > VAULT_MAX_SCAN:
                return _finalize_ob(results)
            full = Path(root) / fn
            try:
                text = full.read_text(encoding="utf-8", errors="ignore")
            except Exception:  # noqa: BLE001
                continue
            if len(text) < 10:
                continue
            raw = _score_text(text, tokens, weights)
            if raw <= 0:
                continue
            # 密度归一：避免长笔记因总命中多而碾压短笔记
            density = raw / (1 + len(text) / 300.0)
            rel = str(full.relative_to(vault)).replace("\\", "/")
            if rel.startswith(PRIORITY_OB_FOLDER):
                density += 0.5  # 业务知识保底加权
            results.append({
                "type": "obsidian",
                "kind": "Obsidian 笔记",
                "title": _first_heading(text) or fn[:-3],
                "ref": rel,
                "snippet": _best_snippet(text, tokens),
                "score": density,
            })
            if len(results) >= VAULT_MAX_SNIPPETS * 4:
                return _finalize_ob(results)
    return _finalize_ob(results)


def _finalize_ob(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # 去重（同文件），按 score 降序，限制上限
    seen = set()
    uniq = []
    for r in sorted(results, key=lambda x: -x["score"]):
        if r["ref"] in seen:
            continue
        seen.add(r["ref"])
        uniq.append(r)
    return uniq[:VAULT_MAX_SNIPPETS]


# ---------------------------------------------------------------------------
# B 档：LLM 查询改写
# ---------------------------------------------------------------------------

REWRITE_SYSTEM = (
    "你是产品经理工作台的检索优化器。用户会用自然语言提问，你需要把问题拆解为用于检索"
    "「项目数据库（需求/工单/会议/运营/知识库）」与「Obsidian 笔记」的关键词与同义表达。"
    "只输出 JSON，不要任何解释。格式："
    '{"terms": ["关键词1", "同义词2"], "queries": ["可在数据库检索的短语1", "短语2"]}。'
    "务必覆盖业务同义与缩写（如 FTTO 联想 光纤到办公室；商客 联想 商业客户；交付 联想 开通受理）。"
)


def _rewrite_query(db: Session, question: str) -> Optional[Dict[str, Any]]:
    """调用统一 LLM 把问题改写为检索词/同义短语；失败返回 None（退回词法召回）。"""
    try:
        res = call_best_available(db, REWRITE_SYSTEM, f"问题：{question}")
    except Exception:  # noqa: BLE001
        return None
    if not res.get("used_llm"):
        return None
    txt = (res.get("text") or "").strip()
    txt = re.sub(r"^```(?:json)?", "", txt).strip()
    txt = re.sub(r"```$", "", txt).strip()
    try:
        obj = json.loads(txt)
    except Exception:  # noqa: BLE001
        return None
    terms = [str(t).strip() for t in (obj.get("terms") or []) if str(t).strip()]
    queries = [str(q).strip() for q in (obj.get("queries") or []) if str(q).strip()]
    if not terms and not queries:
        return None
    return {"terms": terms, "queries": queries}


# ---------------------------------------------------------------------------
# 融合 + 上下文组装 + 问答
# ---------------------------------------------------------------------------

def _fuse(db_list: List[Dict[str, Any]], ob_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """跨源统一归一化打分、融合排序，并保证 Obsidian 保底份额。"""
    db_norm = _normalize([x["score"] for x in db_list])
    ob_norm = _normalize([x["score"] for x in ob_list])
    for i, x in enumerate(db_list):
        x["nscore"] = db_norm[i] * 0.6
    for i, x in enumerate(ob_list):
        x["nscore"] = ob_norm[i] * 0.8  # 略偏向领域知识笔记
    pool = db_list + ob_list
    pool.sort(key=lambda x: -x["nscore"])
    sel = pool[:TOP_K]
    # 保证 Obsidian 保底份额
    ob_in = [x for x in sel if x["type"] == "obsidian"]
    if len(ob_in) < GUARANTEE_OB and ob_list:
        sel_ids = {id(s) for s in sel}
        extra = [x for x in ob_list if id(x) not in sel_ids][: GUARANTEE_OB - len(ob_in)]
        sel = sel + extra
    sel.sort(key=lambda x: -x["nscore"])
    return sel


def _build_context(selected: List[Dict[str, Any]]):
    """合并来源并截断到上下文上限，返回 (numbered_sources, context_text)。"""
    numbered: List[Dict[str, Any]] = []
    ctx_parts: List[str] = []
    chars = 0
    for s in selected:
        block = f"{len(numbered) + 1}. [{s['kind']} {s['ref']}] {s['title']}\n{s['snippet']}"
        if chars + len(block) > CTX_TOTAL_MAX and numbered:
            break
        numbered.append({
            "idx": len(numbered) + 1,
            "type": s["type"],
            "title": s["title"],
            "ref": s["ref"],
            "snippet": s["snippet"],
        })
        ctx_parts.append(block)
        chars += len(block)
    return numbered, "\n\n".join(ctx_parts)


def _build_user_prompt(question: str, context: str, history) -> str:
    parts: List[str] = []
    if history:
        turns = history[-6:]
        hist_lines = []
        for m in turns:
            role = "用户" if m.get("role") == "user" else "助手"
            hist_lines.append(f"{role}：{m.get('content', '')}")
        if hist_lines:
            parts.append("【历史对话】\n" + "\n".join(hist_lines))
    if context:
        parts.append("【检索材料】\n" + context)
    else:
        parts.append("【检索材料】\n（未检索到相关项目数据）")
    parts.append(f"【用户问题】\n{question}")
    return "\n\n".join(parts)


def ask(db: Session, question: str, history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    """基于项目数据库 + Obsidian 笔记智能回答用户问题（A 档 + B 档）。"""
    tokens = tokenize(question)
    if not tokens:
        return {
            "answer": "问题为空或无法提取有效检索词，请换一种表述。",
            "sources": [],
            "used_llm": False,
            "provider_name": None,
            "notice": "无法提取检索词",
            "semantic_rewrite": False,
            "retrieval": {"db_hits": 0, "ob_hits": 0, "used": 0, "semantic_rewrite": False, "top_score": 0},
        }

    # B 档：LLM 查询改写（扩展检索词）；失败则退回原词
    semantic_rewrite = False
    expanded: List[str] = list(tokens)
    rw = _rewrite_query(db, question)
    if rw:
        semantic_rewrite = True
        for t in rw["terms"]:
            expanded.extend(tokenize(t))
        for q in rw["queries"]:
            expanded.extend(tokenize(q))
    syn = expand_synonyms([t for t in expanded if len(t) >= 2])[:50]
    # 词权重：原始问题词 = 1.0，同义/改写扩展词 = 0.5（降低噪声误召回）
    base_set = set(tokens)
    weights = {t: (1.0 if t in base_set else 0.5) for t in syn}

    db_sources = _search_db_scored(db, syn, weights)
    ob_sources = _search_obsidian_scored(syn, weights)
    selected = _fuse(db_sources, ob_sources)
    numbered, context = _build_context(selected)

    retrieval = {
        "db_hits": len(db_sources),
        "ob_hits": len(ob_sources),
        "used": len(numbered),
        "semantic_rewrite": semantic_rewrite,
        "top_score": round(selected[0]["nscore"], 3) if selected else 0,
    }

    if not numbered:
        return {
            "answer": "在项目数据库中未检索到与问题相关的资料。可尝试更换更具体的关键词（如需求编号、产品名、系统名），或确认相关数据已录入。",
            "sources": [],
            "used_llm": False,
            "provider_name": None,
            "notice": "未检索到相关资料",
            "semantic_rewrite": semantic_rewrite,
            "retrieval": retrieval,
        }

    user_prompt = _build_user_prompt(question, context, history)

    res = call_best_available(db, SYSTEM_PROMPT, user_prompt)
    if not res["used_llm"]:
        answer = (
            "当前「大模型管理」中未配置可用模型，无法生成智能回答。"
            "以下是从项目数据中检索到的相关资料，供你参考：\n\n"
            + ("\n".join(f"{s['idx']}. [{s['kind']} {s['ref']}] {s['title']}" for s in numbered) or "（未检索到相关资料）")
        )
        return {
            "answer": answer,
            "sources": numbered,
            "used_llm": False,
            "provider_name": None,
            "notice": res.get("notice"),
            "semantic_rewrite": semantic_rewrite,
            "retrieval": retrieval,
        }

    return {
        "answer": res["text"],
        "sources": numbered,
        "used_llm": True,
        "provider_name": res.get("provider_name"),
        "notice": res.get("notice"),
        "semantic_rewrite": semantic_rewrite,
        "retrieval": retrieval,
    }
