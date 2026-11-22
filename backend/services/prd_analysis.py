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
    REFINE_PROMPT_EXTRA,
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

    def __init__(self, systems: List[str], selected_dirs: Optional[List[str]] = None):
        self.systems = [s for s in systems if s in KNOWN_SYSTEMS] or KNOWN_SYSTEMS[:]
        # 业务子目录筛选：形如 ["CRM/base_custinfo", "ORDER_CENTER/电子协议js-bcm-v2"]；
        # 留空=全部。只接受 sys/dir 两层白名单形态，防目录穿越。
        self.selected_dirs = {
            d.strip().strip("/") for d in (selected_dirs or []) if d and "/" in d
        }
        self.root = Path(settings.PRD_KNOWLEDGE_ROOT)
        self.available = self.root.is_dir()
        self.files: List[Tuple[str, str, str, str]] = []  # (sys_id, repo_id, rel_path, text)

    def load(self) -> int:
        """扫描本地 clone 的 md 文件，返回装载文件数。未 clone 时返回 0（降级无知识）。"""
        if not self.available:
            logger.info("PRD 知识源未 clone（%s 不存在）→ 降级无知识分析", self.root)
            return 0
        # 每个系统均分配额，避免文件最多的系统吃光上限、导致其余系统知识为零。
        # 系统内按「规则/接口/数据/流程」优先排序，保证高价值文档先进上下文。
        per_sys = max(1, settings.PRD_KNOWLEDGE_MAX_SCAN // max(1, len(self.systems)))
        PRIORITY = ("rule", "规则", "api", "接口", "data", "数据", "flow", "流程", "readme", "claude", "spec", "业务")
        for sys_id in self.systems:
            sys_dir = self.root / sys_id
            if not sys_dir.is_dir():
                continue
            sys_count = 0
            # 若页面勾选了业务子目录，只遍历命中的目录，其余跳过
            scoped = [d for d in self.selected_dirs if d.startswith(sys_id + "/")]
            if scoped:
                walk_roots = [self.root / d for d in scoped if (self.root / d).is_dir()]
            else:
                walk_roots = [sys_dir]
            for walk_root in walk_roots:
                for dirpath, dirnames, filenames in os.walk(walk_root):
                    dirnames[:] = [
                        d for d in dirnames
                        if not d.startswith(".") and d not in ("node_modules", "attachments", "images")
                    ]
                    mds = [f for f in filenames if f.lower().endswith(".md")]
                    mds.sort(key=lambda f: not any(k in f.lower() for k in PRIORITY))
                    for fn in mds:
                        if sys_count >= per_sys:
                            break
                        full = Path(dirpath) / fn
                        try:
                            text = full.read_text(encoding="utf-8", errors="ignore")
                        except Exception:  # noqa: BLE001
                            continue
                        if len(text) < 20:
                            continue
                        sys_count += 1
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
    selected_dirs: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """五步编排一次分析，返回结果 dict（同时落库 pmwb_prd_*）。"""
    if not raw_requirement.strip():
        raise ValueError("澄清后需求内容不能为空")

    ticket_meta = _load_ticket_meta(db, req_id)
    req_name = req_name.strip() or ticket_meta.get("req_name") or _resolve_req_name(db, req_id)
    systems = systems or KNOWN_SYSTEMS[:]
    trace_id = f"PRD-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"

    # 步骤 1-2：接需求 + 确认系统（本 Web 形态由前端一次提交，服务端直接采信）
    # 步骤 3：装载本地知识（skill 原样接入的 Git clone，只读）
    ks = KnowledgeSource(systems, selected_dirs=selected_dirs)
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
        prototype=prototype, ticket_meta=ticket_meta,
    )

    # 步骤 5：调用统一 LLM（外网模型由「大模型管理」统一配置，需求文本会外发）
    result = _call_llm_with_fallback(
        db, system_prompt, user_message,
        req_id=req_id, req_name=req_name, systems=systems,
        raw=raw_requirement, answers=answers, meta=ticket_meta,
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
    file_rel = _write_prd_file(
        req_id, req_name, result["prd_markdown"], trace_id, version="v1",
    )

    out = {
        "trace_id": trace_id,
        "req_id": req_id,
        "version": "v1",
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


def _load_ticket_meta(db: Session, req_id: str) -> Dict[str, str]:
    """读需求工单原始信息（单一来源 SentEmail）；缺失字段留空，由 prompt 填 null，绝不编造。"""
    try:
        row = db.query(SentEmail).filter(SentEmail.req_id == req_id).first()
    except Exception as e:  # noqa: BLE001
        logger.warning("读取需求工单元数据失败（不阻断分析）: %s", e)
        return {}
    if not row:
        return {}
    return {
        "req_name": (row.req_name or "").strip(),
        "proposer": (row.proposer or "").strip(),
        "sa_name": (row.sa_name or "").strip(),
        "propose_time": row.propose_time.strftime("%Y-%m-%d") if getattr(row, "propose_time", None) else "",
        "background": (row.background or "").strip(),
        "description": (row.description or "").strip(),
        "origin": (row.origin or "").strip(),
    }


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
    ticket_meta: Optional[Dict[str, str]] = None,
) -> str:
    tm = ticket_meta or {}
    parts = [
        f"【需求编号】{req_id}\n【需求名称】{req_name}\n【涉及系统】{'、'.join(systems)}\n【分析模式】{mode}",
        "【需求工单原始信息（仅作溯源参照，不得覆盖澄清后需求）】\n"
        f"- 提出人：{tm.get('proposer') or '（未提供）'}\n"
        f"- 客户经理/SA：{tm.get('sa_name') or '（未提供）'}\n"
        f"- 提出时间：{tm.get('propose_time') or '（未提供）'}\n"
        f"- 来源：{tm.get('origin') or '（未提供）'}\n"
        f"- 需求背景（原始）：{tm.get('background') or '（未提供）'}\n"
        f"- 需求描述（原始）：{tm.get('description') or '（未提供）'}",
        f"【澄清后需求内容（方案评估与设计目标的唯一业务基准）】\n{raw}",
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
    meta: Optional[Dict[str, str]] = None,
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
        "prd_markdown": fallback_prd(req_id, req_name, systems, raw, answers, meta=meta),
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


def _write_prd_file(
    req_id: str, req_name: str, markdown: str, trace_id: str,
    version: str = "v1",
) -> str:
    """PRD 落到「需求采集 → 需求分析说明书文件夹」同一目录（与 generate-doc 共用路径规则）。

    目录名 {req_id}_{标题40字}、文件名 {标题}PRD-{version}.md；旧版本文件保留留痕。
    失败不阻断主流程（数据库仍留痕）。
    """
    try:
        # 与 requirement_delivery._resolve_paths 共用规则，避免两套命名漂移
        from services.requirement_delivery import _safe_name as _folder_safe_name

        vault = Path(settings.OBSIDIAN_VAULT_PATH)
        folder = vault / settings.REQUIREMENT_DOC_DIR / f"{_safe_name(req_id)}_{_folder_safe_name(req_name or req_id)}"
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"{_folder_safe_name(req_name or req_id)}PRD-{version}.md"
        target.write_text(markdown, encoding="utf-8")
        return str(target.relative_to(vault)).replace("\\", "/")
    except Exception as e:  # noqa: BLE001
        logger.warning("PRD 落盘失败（不影响数据库记录）: %s", e)
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
        "assumptions": _extract_section_lines(row.prd_markdown or "", "假设"),
        "open_items": _extract_open_items(row.prd_markdown or ""),
        "prd_markdown": row.prd_markdown or "",
        "version": (row.prd_file_path or "").rsplit("PRD-", 1)[-1].replace(".md", "") or "v1",
    }


def _extract_open_items(markdown: str) -> List[str]:
    """从 PRD 6.1 段反解待确认点（零迁移：不新增表字段，刷新后仍可二次评估）。"""
    return _extract_section_lines(markdown, "6.1")


def _extract_section_lines(markdown: str, marker: str) -> List[str]:
    """抽取 marker 所在标题段下的 '- ' 列表项；无匹配返回空。"""
    lines = (markdown or "").split("\n")
    out: List[str] = []
    in_section = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            if in_section:
                break
            in_section = marker in stripped
            continue
        if in_section and (stripped.startswith("- ") or stripped.startswith("* ")):
            item = stripped[2:].strip()
            if item and item not in out:
                out.append(item)
    return out[:30]


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


def refine(
    db: Session, trace_id: str, *,
    supplements: List[Dict[str, str]],
    design_notes: str = "",
) -> Dict[str, Any]:
    """二次评估：基于 v1 PRD + 老大逐条补充的待确认点，重新生成 v2 PRD。

    - 旧 trace 行/文件保留留痕；新 trace 行 + PRD-v{N}.md 同目录落盘。
    - LLM 不可用时降级=在 v1 正文后追加本轮补充（不丢 v1 内容），标 status=fallback。
    """
    row = db.query(PmwbPrdAnalysis).filter(PmwbPrdAnalysis.trace_id == trace_id).first()
    if not row:
        raise LookupError(f"分析记录不存在：{trace_id}")
    if not row.prd_markdown:
        raise ValueError("v1 PRD 正文为空，无法二次评估")

    old_md = row.prd_markdown or ""
    version_no = int(re.search(r"version:\s*v(\d+)", old_md).group(1)) + 1 if re.search(r"version:\s*v(\d+)", old_md) else 2
    version = f"v{version_no}"
    req_id, req_name = row.req_id, row.req_name or ""
    supplements = [s for s in (supplements or []) if (s.get("item") or "").strip() or (s.get("answer") or "").strip()]
    if not supplements and not (design_notes or "").strip():
        raise ValueError("未填写任何补充说明，无需二次评估")

    sup_block = "\n".join(
        f"- 待确认项：{s.get('item', '').strip()}\n  本轮补充：{(s.get('answer') or '').strip() or '（未补充）'}"
        for s in supplements
    ) or "- （无逐条补充，仅方案备注）"
    meta = _load_ticket_meta(db, req_id)
    raw = _extract_clarified_content(old_md) or meta.get("description", "")
    answers = json.loads(row.answers or "{}")
    ticket_meta_block = (
        f"- 提出人：{meta.get('proposer') or '（未提供）'}\n"
        f"- 客户经理/SA：{meta.get('sa_name') or '（未提供）'}"
    )

    system_prompt = (
        PRD_SYSTEM_PROMPT + BUSINESS_VS_TECH_RULES + REFINE_PROMPT_EXTRA
        + "\n【PRD 六章结构（不得增减章名）】\n" + "\n".join(f"- {c}" for c in PRD_CHAPTERS)
        + "\n【YAML frontmatter 十二键】" + "、".join(FRONTMATTER_KEYS)
    )
    if row.profile == "deep":
        system_prompt += "\n" + PROFILE_DEEP_EXTRA
    user_message = (
        f"【需求编号】{req_id}\n【需求名称】{req_name}\n"
        f"【需求工单元数据（溯源参照）】\n{ticket_meta_block}\n\n"
        f"【澄清后需求内容（唯一业务基准）】\n{raw}\n\n"
        f"【v1 PRD 全文（底稿，不得回退已确认结论）】\n{old_md}\n\n"
        f"【本轮逐条补充（覆盖 v1 对应待确认项）】\n{sup_block}\n\n"
        f"【方案备注】\n{(design_notes or '').strip() or '（无）'}\n\n"
        "请严格按 system 指令输出唯一 JSON 对象，version 递增，6.2 变更记录写明本轮变化。"
    )

    new_trace = f"PRD-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
    result = _call_llm_with_fallback(
        db, system_prompt, user_message,
        req_id=req_id, req_name=req_name,
        systems=json.loads(row.systems or "[]"), raw=raw, answers=answers, meta=meta,
    )
    if result.get("status") == "fallback":
        # 二次评估降级：保留 v1 底稿 + 追加本轮补充，不生成空骨架
        md = _append_refine_note(old_md, version, sup_block, design_notes)
        result["prd_markdown"] = md
        result["open_items"] = _extract_open_items(md)
        result["gen_fallback_reason"] = (
            (result.get("gen_fallback_reason") or "") + "；二次评估保留 v1 底稿并追加补充说明"
        )
    else:
        # 确保版本号递增（LLM 可能没按 prompt 改）
        result["prd_markdown"] = _force_version(result["prd_markdown"], old_md, version)

    _persist(
        db, trace_id=new_trace, req_id=req_id, req_name=req_name,
        mode=row.mode or "qa", profile=row.profile or "concise",
        systems=json.loads(row.systems or "[]"), answers=answers,
        result=result,
        sources=[{
            "sys_id": s.sys_id or "", "repo_id": s.repo_id or "", "sha": s.sha or "",
            "path": s.path or "", "clause": s.clause or "", "quote": s.quote or "",
        } for s in (db.query(PmwbPrdSource).filter(PmwbPrdSource.trace_id == trace_id).all())],
        n_files=row.knowledge_files or 0, knowledge_mode=row.knowledge_mode or "none",
    )
    file_rel = _write_prd_file(req_id, req_name, result["prd_markdown"], new_trace, version=version)
    if file_rel:
        new_row = db.query(PmwbPrdAnalysis).filter(PmwbPrdAnalysis.trace_id == new_trace).first()
        if new_row:
            new_row.prd_file_path = file_rel
            db.commit()

    return {
        "trace_id": new_trace,
        "parent_trace_id": trace_id,
        "version": version,
        "req_id": req_id,
        "prd_markdown": result["prd_markdown"],
        "conflicts": result.get("conflicts") or [],
        "sources": [{
            "sys_id": s.sys_id or "", "repo_id": s.repo_id or "", "sha": s.sha or "",
            "path": s.path or "", "clause": s.clause or "", "quote": s.quote or "",
        } for s in db.query(PmwbPrdSource).filter(PmwbPrdSource.trace_id == new_trace).all()],
        "assumptions": result.get("assumptions") or [],
        "open_items": result.get("open_items") or [],
        "status": result["status"],
        "gen_strategy": result["gen_strategy"],
        "gen_provider": result.get("gen_provider"),
        "gen_model": result.get("gen_model"),
        "gen_fallback_reason": result.get("gen_fallback_reason"),
        "knowledge_mode": row.knowledge_mode or "none",
        "knowledge_files": row.knowledge_files or 0,
        "notice": (f"基于 v1 二次评估生成 {version}；v1 文件保留留痕。"),
    }


def _extract_clarified_content(markdown: str) -> str:
    """从 v1 PRD 的 1.1 澄清后需求内容段反解业务基准（零迁移）。"""
    lines = (markdown or "").split("\n")
    out: List[str] = []
    in_section = False
    for line in lines:
        s = line.strip()
        if s.startswith("#"):
            if in_section:
                break
            in_section = "澄清后需求内容" in s
            continue
        if in_section and s and not s.startswith(">"):
            out.append(s)
    return "\n".join(out).strip()


def _force_version(markdown: str, old_md: str, version: str) -> str:
    """确保 v2 frontmatter version 递增；未递增则强制替换 + 6.2 补记。"""
    if re.search(r"^version:\s*v\d+\s*$", markdown, re.M):
        markdown = re.sub(r"^version:\s*v\d+\s*$", f"version: {version}", markdown, count=1, flags=re.M)
    else:
        markdown = re.sub(r"^(---\s*\n)", rf"\1version: {version}\n", markdown, count=1)
    if "本轮变化" not in markdown:
        note = f"- {version} 本轮变化：基于老大逐条补充的待确认点与方案备注二次评估生成。"
        marker = "### 6.2 变更记录"
        if marker in markdown:
            markdown = markdown.replace(marker, marker + "\n" + note, 1)
        else:
            markdown += f"\n\n{marker}\n" + note
    return markdown


def _append_refine_note(old_md: str, version: str, sup_block: str, design_notes: str) -> str:
    """降级路径：v1 底稿 + 追加本轮补充，不丢已确认内容。"""
    md = _force_version(old_md, old_md, version)
    md += (
        f"\n\n## 附：{version} 二次评估补充（大模型不可用，规则追加）\n\n"
        f"### 本轮逐条补充\n{sup_block}\n\n"
        f"### 方案备注\n{(design_notes or '').strip() or '（无）'}\n\n"
        "> 本段为老大本轮补充说明的原文登记；待大模型恢复后可重新二次评估生成完整 v2 六章。\n"
    )
    return md


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
            synced_at = data.get("generated_at") or data.get("synced_at") or data.get("updated_at")
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
