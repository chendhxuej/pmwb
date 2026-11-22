"""PRD 需求分析 service（移植外部 prd-workflow skill 的 Web 一次性分析形态）。

设计要点：
- 五步编排：接需求 → 确认系统 → 装载知识 → 十维问卷自决 → 生成交付 PRD.md。
- 知识源抽象 KnowledgeSource：skill 原样接入 = 只读本地 Git clone（D:\\项目\\knowledge）；
  未 clone / 不可读时自动降级为无知识分析，不阻塞 PRD 生成。
- 检索复用 ai_qa 的密度打分思路（同文件内实现，避免依赖 ai_qa 私有函数），Top-N 入上下文，不灌全量。
- LLM 复用 services.llm_provider.call_best_available（「大模型管理」统一注册表，含外网模型）；
  全失败降级规则模板 PRD，gen_* 溯源可见。
- 落位：结构化数据 MySQL（本 service 写 pmwb_prd_*）；PRD.md 写 D:\\项目\\ 下（禁写 C 盘）。
"""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from constants.prd_prompt import (
    BUSINESS_VS_TECH_RULES,
    FRONTMATTER_KEYS,
    NO_KNOWLEDGE_NOTE,
    PRD_CHAPTERS,
    PRD_SYSTEM_PROMPT,
    PROFILE_DEEP_EXTRA,
    TEN_DIMENSIONS,
    fallback_prd,
)
from core.config import settings
from db.models import PmwbPrdAnalysis, PmwbPrdConflict, PmwbPrdSource, SentEmail
from db.models import now_cn

logger = logging.getLogger(__name__)

# 系统注册表 ID（与 skill references/system-knowledge-map.json 一致）
KNOWN_SYSTEMS = ["CRM", "BOSS", "ORDER_CENTER"]
MAX_RETRIES = 2
CTX_MAX_CHARS = 12000  # 知识上下文上限（与 ai_qa 的 13000 同量级）


# ===========================================================================
# 知识源抽象（唯一入口：切换 Git clone / 无知识 只改这里）
# ===========================================================================
class KnowledgeSource:
    """只读知识源。skill 原样接入 = 本地 Git clone。

    不执行 Git、不处理凭据（GCM 凭据仅存老大本机 Windows 凭据管理器，服务端零落盘）。
    """

    def __init__(self, systems: List[str]):
        self.systems = [s for s in systems if s in KNOWN_SYSTEMS] or KNOWN_SYSTEMS[:]
        self.root = Path(settings.PRD_KNOWLEDGE_ROOT)
        self.available = self.root.is_dir()
        self.files: List[Tuple[str, str, str, str]] = []  # (sys_id, repo_id, rel_path, text)

    def load(self) -> int:
        """扫描本地 clone 的 md 文件，返回装载文件数。未 clone 时返回 0（降级无知识）。"""
        if not self.available:
            logger.info("PRD 知识源未 clone（%s 不存在）→ 降级无知识分析", self.root)
            return 0
        scanned = 0
        max_scan = settings.PRD_KNOWLEDGE_MAX_SCAN
        for sys_id in self.systems:
            sys_dir = self.root / sys_id
            if not sys_dir.is_dir():
                continue
            for dirpath, dirnames, filenames in os.walk(sys_dir):
                dirnames[:] = [
                    d for d in dirnames
                    if not d.startswith(".") and d not in ("node_modules", "attachments", "images")
                ]
                for fn in filenames:
                    if not fn.lower().endswith(".md"):
                        continue
                    scanned += 1
                    if scanned > max_scan:
                        break
                    full = Path(dirpath) / fn
                    try:
                        text = full.read_text(encoding="utf-8", errors="ignore")
                    except Exception:  # noqa: BLE001
                        continue
                    if len(text) < 20:
                        continue
                    rel = str(full.relative_to(self.root)).replace("\\", "/")
                    repo_id = rel.split("/")[1] if len(rel.split("/")) > 1 else sys_id
                    self.files.append((sys_id, repo_id, rel, text))
        logger.info("PRD 知识源装载：%d 个文件（clone=%s）", len(self.files), self.root)
        return len(self.files)

    def retrieve(self, tokens: List[str]) -> Tuple[str, List[Dict[str, str]]]:
        """按命中密度打分取 Top-N，返回（上下文文本, 来源元数据）。"""
        if not self.files or not tokens:
            return "", []
        scored: List[Dict[str, Any]] = []
        for sys_id, repo_id, rel, text in self.files:
            hits = sum(text.lower().count(t.lower()) for t in tokens)
            if hits <= 0:
                continue
            density = hits / (1 + len(text) / 400.0)
            snippet = _best_snippet(text, tokens)
            scored.append({
                "sys_id": sys_id, "repo_id": repo_id, "path": rel,
                "snippet": snippet, "score": density,
            })
        scored.sort(key=lambda x: -x["score"])
        picked = scored[: settings.PRD_KNOWLEDGE_MAX_SNIPPETS]
        lines: List[str] = []
        sources: List[Dict[str, str]] = []
        total = 0
        for i, s in enumerate(picked, 1):
            block = f"[K{i}] 系统={s['sys_id']} 仓库={s['repo_id']} 路径={s['path']}\n{s['snippet'][:700]}"
            if total + len(block) > CTX_MAX_CHARS:
                break
            lines.append(block)
            total += len(block)
            sources.append({
                "sys_id": s["sys_id"], "repo_id": s["repo_id"],
                "path": s["path"], "clause": "命中片段", "quote": s["snippet"][:300],
            })
        return "\n\n".join(lines), sources


def _best_snippet(text: str, tokens: List[str], window: int = 700) -> str:
    """取命中密度最高的一段（滑动窗口）。"""
    if not tokens:
        return text[:window]
    low = text.lower()
    best_start, best_hits = 0, -1
    step = max(1, window // 4)
    for start in range(0, max(1, len(text) - window + 1), step):
        seg = low[start:start + window]
        hits = sum(seg.count(t.lower()) for t in tokens)
        if hits > best_hits:
            best_hits, best_start = hits, start
    return text[best_start:best_start + window].strip()


def _extract_tokens(text: str) -> List[str]:
    """从需求文本提取检索词：中文 2-6 字短语 + 英文/数字标识。"""
    tokens = set(re.findall(r"[A-Za-z0-9_]{2,}", text))
    for seg in re.findall(r"[\u4e00-\u9fff]+", text):
        for n in (2, 3, 4):
            for i in range(len(seg) - n + 1):
                tokens.add(seg[i:i + n])
    # 过滤过泛词，控制规模
    stop = {"我们", "需要", "可以", "一个", "这个", "进行", "相关", "已经", "要求", "系统", "用户", "业务"}
    tokens = {t for t in tokens if t not in stop and len(t) >= 2}
    return sorted(tokens, key=len, reverse=True)[:60]


# ===========================================================================
# 编排
# ===========================================================================
def analyze(
    db: Session,
    req_id: str,
    *,
    raw_requirement: str,
    systems: List[str],
    mode: str,
    profile: str,
    answers: Dict[str, str],
    req_name: str = "",
    special_notes: str = "",
    prototype: bool = False,
) -> Dict[str, Any]:
    """五步编排一次分析，返回结果 dict（同时落库 pmwb_prd_*）。"""
    if not raw_requirement.strip():
        raise ValueError("澄清后需求内容不能为空")

    req_name = req_name.strip() or _resolve_req_name(db, req_id)
    systems = systems or KNOWN_SYSTEMS[:]
    trace_id = f"PRD-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"

    # 步骤 1-2：接需求 + 确认系统（本 Web 形态由前端一次提交，服务端直接采信）
    # 步骤 3：装载本地知识（skill 原样接入的 Git clone，只读）
    ks = KnowledgeSource(systems)
    n_files = ks.load()
    tokens = _extract_tokens(raw_requirement + " " + " ".join(answers.values()))
    knowledge_ctx, knowledge_sources = ks.retrieve(tokens)
    knowledge_mode = "git" if n_files > 0 else "none"

    # 步骤 4：十维问卷自决（answers 来自前端一次性问卷；未答维度由 LLM 按规则自决/记假设）
    answers_block = _format_answers(answers)
    system_prompt = PRD_SYSTEM_PROMPT + BUSINESS_VS_TECH_RULES
    system_prompt += "\n【PRD 六章结构（不得增减章名）】\n" + "\n".join(f"- {c}" for c in PRD_CHAPTERS)
    system_prompt += "\n【YAML frontmatter 八键】" + "、".join(FRONTMATTER_KEYS)
    if profile == "deep":
        system_prompt += "\n" + PROFILE_DEEP_EXTRA
    if knowledge_mode == "none":
        system_prompt += "\n\n【知识装载状态】" + NO_KNOWLEDGE_NOTE

    user_message = _build_user_message(
        req_id=req_id, req_name=req_name, raw=raw_requirement,
        systems=systems, mode=mode, answers_block=answers_block,
        knowledge_ctx=knowledge_ctx, special_notes=special_notes,
        prototype=prototype,
    )

    # 步骤 5：调用统一 LLM（外网模型由「大模型管理」统一配置，需求文本会外发）
    result = _call_llm_with_fallback(
        db, system_prompt, user_message,
        req_id=req_id, req_name=req_name, systems=systems,
        raw=raw_requirement, answers=answers,
    )

    # 来源：LLM 返回的 sources 优先；无知识时为空；保留检索命中的真实路径供追溯
    sources = result.get("sources") or []
    if not sources and knowledge_sources:
        sources = [{**s, "sha": "", "clause": "命中片段"} for s in knowledge_sources]

    # 落库 + 写文件
    _persist(
        db, trace_id=trace_id, req_id=req_id, req_name=req_name,
        mode=mode, profile=profile, systems=systems, answers=answers,
        result=result, sources=sources, n_files=n_files,
        knowledge_mode=knowledge_mode,
    )
    file_rel = _write_prd_file(req_id, req_name, result["prd_markdown"], trace_id)

    out = {
        "trace_id": trace_id,
        "req_id": req_id,
        "prd_markdown": result["prd_markdown"],
        "conflicts": result.get("conflicts") or [],
        "sources": sources,
        "assumptions": result.get("assumptions") or [],
        "open_items": result.get("open_items") or [],
        "status": result["status"],
        "gen_strategy": result["gen_strategy"],
        "gen_provider": result.get("gen_provider"),
        "gen_model": result.get("gen_model"),
        "gen_fallback_reason": result.get("gen_fallback_reason"),
        "knowledge_mode": knowledge_mode,
        "knowledge_files": n_files,
        "notice": "",
    }
    # notice 组装（无知识 + 降级均可见）
    notices: List[str] = []
    if knowledge_mode == "none":
        notices.append(NO_KNOWLEDGE_NOTE)
    if result.get("notice"):
        notices.append(result["notice"])
    out["notice"] = " ".join(notices)
    # 更新落盘路径
    if file_rel:
        row = db.query(PmwbPrdAnalysis).filter(PmwbPrdAnalysis.trace_id == trace_id).first()
        if row:
            row.prd_file_path = file_rel
            db.commit()
    return out


def _resolve_req_name(db: Session, req_id: str) -> str:
    row = db.query(SentEmail).filter(SentEmail.req_id == req_id).first()
    return (row.req_name if row else "") or f"需求 {req_id}"


def _format_answers(answers: Dict[str, str]) -> str:
    if not answers:
        return "（未提供问卷答案；请按业务质量规则自行判定 known / 假设 / deferred，不得伪造已确认结论。）"
    lines: List[str] = []
    for dim in TEN_DIMENSIONS:
        key = dim["key"]
        val = answers.get(key)
        if val:
            lines.append(f"- 【{dim['name']}】{dim['hint']} → 已答：{val}")
        else:
            lines.append(f"- 【{dim['name']}】{dim['hint']} → 未答（自行判定并记假设/待确认）")
    return "\n".join(lines)


def _build_user_message(
    *, req_id: str, req_name: str, raw: str, systems: List[str],
    mode: str, answers_block: str, knowledge_ctx: str,
    special_notes: str, prototype: bool,
) -> str:
    parts = [
        f"【需求编号】{req_id}\n【需求名称】{req_name}\n【涉及系统】{'、'.join(systems)}\n【分析模式】{mode}",
        f"【原始需求原文（未改写）】\n{raw}",
        f"【十维问卷答案（一次性提交，非逐轮）】\n{answers_block}",
    ]
    if special_notes:
        parts.append(f"【特殊要求】\n{special_notes}")
    parts.append(
        f"【知识材料（编号 [K*]，仅依据这些材料引用）】\n{knowledge_ctx or '（未装载系统知识）'}"
    )
    if prototype:
        parts.append("【附加要求】本需求涉及界面，请在 PRD 第 2 章补充界面与交互的业务描述（不生成 HTML 代码）。")
    parts.append(
        "请严格按 system 指令输出唯一 JSON 对象。prd_markdown 必须是完整六章 PRD（含 YAML frontmatter）。"
    )
    return "\n\n".join(parts)


def _call_llm_with_fallback(
    db: Session, system_prompt: str, user_message: str, *,
    req_id: str, req_name: str, systems: List[str], raw: str, answers: Dict[str, str],
) -> Dict[str, Any]:
    """复用统一大模型，解析失败重试；全失败降级规则模板。"""
    from services.llm_provider import call_best_available

    last_err = ""
    for attempt in range(MAX_RETRIES + 1):
        try:
            res = call_best_available(db, system_prompt, user_message, max_tokens=12000, timeout=300)
        except Exception as e:  # noqa: BLE001
            last_err = f"大模型调用异常：{str(e)[:200]}"
            logger.warning("PRD LLM 调用异常: %s", e)
            break
        if not res.get("used_llm"):
            last_err = res.get("notice") or "所有已启用大模型不可用"
            break
        provider = res.get("provider_name") or ""
        model = res.get("model") or ""
        try:
            parsed = _parse_llm_json(res.get("text", ""))
            prd_md = (parsed.get("prd_markdown") or "").strip()
            if not prd_md or "## 1" not in prd_md:
                raise ValueError("PRD 正文缺失或六章结构不完整")
            return {
                "prd_markdown": prd_md,
                "conflicts": _sanitize_list(parsed.get("conflicts"), ["level", "type", "desc"]),
                "sources": _sanitize_list(parsed.get("sources"), ["sys_id", "repo_id", "path"]),
                "assumptions": [str(x) for x in (parsed.get("assumptions") or [])][:50],
                "open_items": [str(x) for x in (parsed.get("open_items") or [])][:50],
                "status": "generated",
                "gen_strategy": "llm",
                "gen_provider": provider,
                "gen_model": model,
            }
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            last_err = str(e)
            logger.warning("PRD AI 输出解析失败（%s/%s 第 %d 次）: %s", provider, model, attempt + 1, last_err[:150])

    # 降级：规则模板
    reason = f"AI 分析降级为规则模板（已重试 {MAX_RETRIES} 次）：{last_err}"
    logger.warning(reason)
    return {
        "prd_markdown": fallback_prd(req_id, req_name, systems, raw, answers),
        "conflicts": [],
        "sources": [],
        "assumptions": [],
        "open_items": [NO_KNOWLEDGE_NOTE],
        "status": "fallback",
        "gen_strategy": "rules_fallback",
        "gen_provider": None,
        "gen_model": None,
        "gen_fallback_reason": reason,
        "notice": reason,
    }


def _parse_llm_json(text: str) -> Dict[str, Any]:
    """兼容 ```json 代码块 / 前后解释文字，提取第一个完整 JSON 对象。"""
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    if start < 0:
        raise ValueError("AI 输出无 JSON 对象")
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    raise ValueError("AI 输出 JSON 不完整")


def _sanitize_list(value: Any, required_keys: List[str]) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    out: List[Dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict) and any(k in item for k in required_keys):
            out.append({k: str(item.get(k, "") or "") for k in (
                "level", "type", "desc", "evidence", "sys_id", "repo_id", "sha", "path", "clause", "quote"
            )})
    return out[:60]


def _persist(
    db: Session, *, trace_id: str, req_id: str, req_name: str,
    mode: str, profile: str, systems: List[str], answers: Dict[str, str],
    result: Dict[str, Any], sources: List[Dict[str, str]], n_files: int,
    knowledge_mode: str,
) -> None:
    row = PmwbPrdAnalysis(
        trace_id=trace_id, req_id=req_id, req_name=req_name,
        mode=mode, profile=profile,
        systems=json.dumps(systems, ensure_ascii=False),
        answers=json.dumps(answers, ensure_ascii=False),
        prd_markdown=result["prd_markdown"],
        status=result["status"],
        gen_strategy=result["gen_strategy"],
        gen_provider=result.get("gen_provider"),
        gen_model=result.get("gen_model"),
        gen_fallback_reason=result.get("gen_fallback_reason"),
        knowledge_mode=knowledge_mode,
        knowledge_files=n_files,
        notice=(result.get("notice") or "")[:2000],
        created_at=now_cn(),
    )
    db.add(row)
    for s in sources:
        db.add(PmwbPrdSource(
            trace_id=trace_id,
            sys_id=s.get("sys_id", ""), repo_id=s.get("repo_id", ""),
            sha=s.get("sha", ""), path=s.get("path", ""),
            clause=s.get("clause", ""), quote=(s.get("quote") or "")[:2000],
            created_at=now_cn(),
        ))
    for c in (result.get("conflicts") or []):
        db.add(PmwbPrdConflict(
            trace_id=trace_id,
            level=c.get("level", ""), type=c.get("type", ""),
            desc=(c.get("desc") or "")[:2000], evidence=(c.get("evidence") or "")[:2000],
            created_at=now_cn(),
        ))
    db.commit()


def _write_prd_file(req_id: str, req_name: str, markdown: str, trace_id: str) -> str:
    """PRD.md 落 D:\\项目\\ 下（禁写 C 盘）；失败不阻断主流程。"""
    try:
        vault = Path(settings.OBSIDIAN_VAULT_PATH)
        doc_dir = vault / settings.REQUIREMENT_DOC_DIR / _safe_name(req_id)
        doc_dir.mkdir(parents=True, exist_ok=True)
        target = doc_dir / "PRD.md"
        target.write_text(markdown, encoding="utf-8")
        return str(target.relative_to(vault)).replace("\\", "/")
    except Exception as e:  # noqa: BLE001
        logger.warning("PRD.md 落盘失败（不影响数据库记录）: %s", e)
        return ""


def _safe_name(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", (name or "unknown").strip())[:120]


# ===========================================================================
# 查询 / 收尾
# ===========================================================================
def latest_status(db: Session, req_id: str) -> Optional[Dict[str, Any]]:
    row = (db.query(PmwbPrdAnalysis)
           .filter(PmwbPrdAnalysis.req_id == req_id)
           .order_by(PmwbPrdAnalysis.created_at.desc())
           .first())
    if not row:
        return None
    return {
        "trace_id": row.trace_id, "req_id": row.req_id, "status": row.status,
        "gen_strategy": row.gen_strategy or "", "gen_provider": row.gen_provider,
        "gen_model": row.gen_model,
        "finalized": bool(row.finalized),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def get_result(db: Session, trace_id: str) -> Dict[str, Any]:
    row = db.query(PmwbPrdAnalysis).filter(PmwbPrdAnalysis.trace_id == trace_id).first()
    if not row:
        raise LookupError(f"分析记录不存在：{trace_id}")
    sources = (db.query(PmwbPrdSource).filter(PmwbPrdSource.trace_id == trace_id).all())
    conflicts = (db.query(PmwbPrdConflict).filter(PmwbPrdConflict.trace_id == trace_id).all())
    return {
        "trace_id": row.trace_id, "req_id": row.req_id,
        "sources": [{
            "sys_id": s.sys_id or "", "repo_id": s.repo_id or "", "sha": s.sha or "",
            "path": s.path or "", "clause": s.clause or "", "quote": s.quote or "",
        } for s in sources],
        "conflicts": [{
            "level": c.level or "", "type": c.type or "",
            "desc": c.desc or "", "evidence": c.evidence or "",
        } for c in conflicts],
        "assumptions": [], "open_items": [],
        "prd_markdown": row.prd_markdown or "",
    }


def finalize(db: Session, trace_id: str) -> Dict[str, Any]:
    row = db.query(PmwbPrdAnalysis).filter(PmwbPrdAnalysis.trace_id == trace_id).first()
    if not row:
        raise LookupError(f"分析记录不存在：{trace_id}")
    if not row.prd_markdown:
        raise ValueError("PRD 正文为空，无法确认落库")
    row.finalized = 1
    row.finalized_at = now_cn()
    db.commit()
    return {"trace_id": trace_id, "req_id": row.req_id, "finalized": True,
            "file_path": row.prd_file_path or ""}


def knowledge_status() -> Dict[str, Any]:
    """知识源状态（读 manifest.json，不执行 Git、不接触凭据）。"""
    root = Path(settings.PRD_KNOWLEDGE_ROOT)
    manifest = root / "manifest.json"
    synced_at = None
    mode = "none"
    files = 0
    if root.is_dir():
        mode = "git"
        for dirpath, _dirs, filenames in os.walk(root):
            files += sum(1 for f in filenames if f.lower().endswith(".md"))
            if files > settings.PRD_KNOWLEDGE_MAX_SCAN:
                break
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8", errors="ignore"))
            synced_at = data.get("synced_at") or data.get("updated_at")
        except Exception:  # noqa: BLE001
            pass
    return {
        "knowledge_status": mode,
        "knowledge_root": str(root),
        "knowledge_synced_at": synced_at,
        "knowledge_files": files,
    }


def meta(db: Session) -> Dict[str, Any]:
    """一次性问卷元数据（十维 + 系统 + 知识状态 + LLM 可用性），单一真相源。"""
    from services.llm_provider import get_status
    ks = knowledge_status()
    llm = get_status(db)
    return {
        "dimensions": TEN_DIMENSIONS,
        "systems": KNOWN_SYSTEMS,
        **ks,
        "llm_available": bool(llm.get("available")),
        "llm_notice": llm.get("notice") or "",
    }
