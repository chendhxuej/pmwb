# -*- coding: utf-8 -*-
"""规则沉淀服务（知识中心 · 系统侧核心能力）。

把「自动识别的业务规则」**智能归类**后，幂等沉淀到对应业务领域主笔记的
「场景规则（自动区）」章节。

设计要点
--------
1. **规则来源**：需求用户故事的业务规则（``pmwb_user_story.rules``，JSON 数组）。
   通过 ``req_id`` 关联 ``pmwb_requirement_ext.domain_code`` 定位归属业务领域。
2. **智能归类**：
   - 一级归类 = 业务领域（按需求的 domain_code 归到该领域主笔记）；
   - 二级归类 = 场景类别（按关键词把规则归入 资费/开通/工单/权限/数据/接口/变更/风控）。
3. **幂等**：每条规则渲染时带稳定指纹 ``<!-- rule:story-{story_id}-{idx} -->``，
   重复沉淀不会堆积重复条目；已沉淀过的规则不再计入「待沉淀」。
4. **人工区零覆盖**：只改写 ``PMWB:AUTO`` 标记之间的内容，人工维护区永不被动。
5. **单一真相源**：``sync_main_note_from_links`` 的 场景规则 自动区也改为调用本模块的
   :func:`render_scenario_rules_block`，避免两个口径互相覆盖。

依赖方向：本模块只依赖 db.models / utils.obsidian，不反向依赖 knowledge_link_service，
由后者 import 本模块，避免循环导入。
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set

from db.models import (
    PmwbBusinessDomain,
    PmwbKnowledgeItem,
    PmwbRequirementExt,
    PmwbUserStory,
)
from utils.obsidian import read_markdown, write_markdown

# 自动区标记 key（与 sync_main_note_from_links 的 scenario_rules 保持一致，
# 使「一键同步主笔记」与「规则沉淀」写入同一块，避免双份内容互相覆盖）
RULE_BLOCK_KEY = "scenario_rules"

# ── 场景类别关键词表（按顺序优先匹配，未命中落「通用」）──
RULE_CATEGORY_KEYWORDS = [
    ("资费", ["资费", "价格", "套餐", "折扣", "费用", "收费", "计费", "报价", "减免"]),
    ("开通", ["开通", "受理", "装机", "激活", "竣工", "交付", "施工", "预约"]),
    ("工单", ["工单", "派单", "流转", "退单", "撤单", "催办", "时限", "SLA"]),
    ("权限", ["权限", "角色", "账号", "认证", "授权", "登录", "审批"]),
    ("数据", ["数据", "同步", "清洗", "口径", "统计", "报表", "指标"]),
    ("接口", ["接口", "API", "报文", "字段", "协议", "回调", "参数"]),
    ("变更", ["变更", "调整", "下线", "上线", "切换", "迁移", "升级"]),
    ("风控", ["风控", "合规", "审计", "限制", "校验失败", "拦截", "预警"]),
]
DEFAULT_CATEGORY = "通用"

# 已沉淀规则指纹：<!-- rule:story-{story_id}-{idx} -->
_FP_PATTERN = re.compile(r"<!--\s*rule:story-(\d+)-(\d+)\s*-->")

_AUTO_BEGIN = "<!-- PMWB:AUTO:BEGIN key={key} -->"
_AUTO_END = "<!-- PMWB:AUTO:END key={key} -->"


# ---------------------------------------------------------------------------
# 自动区标记块工具（与 knowledge_link_service._auto_block/_replace_auto_block 同协议，
# 此处本地实现以避免循环导入）
# ---------------------------------------------------------------------------
def _auto_block(key: str, body: str = "") -> str:
    """生成一对自动区标记包裹的块。"""
    begin = _AUTO_BEGIN.format(key=key)
    end = _AUTO_END.format(key=key)
    return f"{begin}\n{body}{end}"


def _replace_auto_block(content: str, key: str, body: str) -> str:
    """替换指定 key 的自动区内容（保留标记，不匹配则原样返回）。"""
    begin = _AUTO_BEGIN.format(key=key)
    end = _AUTO_END.format(key=key)
    pattern = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.DOTALL)
    replacement = f"{begin}\n{body.rstrip(chr(10))}\n{end}"
    return pattern.sub(replacement, content, count=1)


def _block_pattern(key: str):
    begin = _AUTO_BEGIN.format(key=key)
    end = _AUTO_END.format(key=key)
    return re.compile(re.escape(begin) + r".*?" + re.escape(end), re.DOTALL)


def _upsert_auto_block(content: str, key: str, body: str) -> str:
    """写入（upsert）指定 key 的自动区：存在则原地替换并清理重复块，不存在则新建章节。

    历史文件里可能因多次写入堆积了多个同名块（导致同一份规则重复渲染），
    这里统一收敛为**唯一一块**，保证幂等。
    """
    replacement = (
        f"{_AUTO_BEGIN.format(key=key)}\n{body.rstrip(chr(10))}\n{_AUTO_END.format(key=key)}"
    )
    pattern = _block_pattern(key)
    matches = list(pattern.finditer(content))
    if not matches:
        return _ensure_scenario_rules_section(content, body)

    # 首个块原地替换，其余重复块全部删除（倒序删避免偏移）
    out = content[: matches[0].start()] + replacement + content[matches[0].end():]
    rest = list(pattern.finditer(out))
    for m in reversed(rest[1:]):
        out = out[: m.start()] + out[m.end():]
    # 收敛删除后留下的连续空行
    return re.sub(r"\n{3,}", "\n\n", out)


def _has_auto_block(content: str, key: str) -> bool:
    return _AUTO_BEGIN.format(key=key) in content


# ---------------------------------------------------------------------------
# 规则识别与归类
# ---------------------------------------------------------------------------
def classify_rule(text: str) -> str:
    """按关键词把一条规则归入场景类别（未命中返回「通用」）。"""
    s = (text or "").strip()
    if not s:
        return DEFAULT_CATEGORY
    for cat, keywords in RULE_CATEGORY_KEYWORDS:
        for kw in keywords:
            if kw in s:
                return cat
    return DEFAULT_CATEGORY


def _parse_rules(raw) -> List[str]:
    """把 user_story.rules（JSON 数组字符串 / list）解析为规则文本列表。"""
    import json

    if not raw:
        return []
    arr = raw
    if isinstance(arr, str):
        try:
            arr = json.loads(arr)
        except Exception:
            return []
    if not isinstance(arr, list):
        return []
    out = []
    for r in arr:
        if isinstance(r, str):
            t = r.strip()
        elif isinstance(r, dict):
            t = str(r.get("text") or r.get("rule") or r.get("desc") or "").strip()
        else:
            t = str(r).strip()
        if t and t not in ("[]", "null"):
            out.append(t)
    return out


def collect_rules(db, domain_code: Optional[str] = None) -> Dict[str, List[dict]]:
    """扫描全部用户故事业务规则，按业务领域归类。

    返回 {domain_code: [ {story_id, idx, text, category, req_id, req_name, story_title, domain_code} ]}
    只纳入「需求已设置 domain_code」的规则，无法归类的丢弃（不做无主沉淀）。
    """
    q = (
        db.query(PmwbUserStory, PmwbRequirementExt)
        .join(PmwbRequirementExt, PmwbRequirementExt.req_id == PmwbUserStory.req_id)
        .filter(PmwbRequirementExt.domain_code.isnot(None))
    )
    if domain_code:
        q = q.filter(PmwbRequirementExt.domain_code == domain_code)

    result: Dict[str, List[dict]] = {}
    for story, req in q.all():
        rules = _parse_rules(story.rules)
        if not rules:
            continue
        code = req.domain_code
        bucket = result.setdefault(code, [])
        for idx, text in enumerate(rules):
            bucket.append({
                "story_id": story.id,
                "idx": idx,
                "fingerprint": f"story-{story.id}-{idx}",
                "text": text,
                "category": classify_rule(text),
                "req_id": req.req_id,
                "req_name": req.req_name or "",
                "story_title": story.title or "",
                "domain_code": code,
            })
    return result


def sedimented_fingerprints(content: str) -> Set[str]:
    """从主笔记正文解析已沉淀规则的指纹集合。"""
    if not content:
        return set()
    return {f"story-{m.group(1)}-{m.group(2)}" for m in _FP_PATTERN.finditer(content)}


# 历史规则（无 fingerprint 但包含需求编号）正则
_HIST_RULE_PAT = re.compile(
    r"^[-*]\s*(.+?)\s*（敏捷需求[^\)]+\）\s*$",
    re.MULTILINE,
)


def scan_historical_rules(content: str) -> List[dict]:
    """扫描主笔记自动区内缺少指纹的历史规则。

    返回 [{text, req_id}] 列表。text 为规则正文，req_id 为括号中的需求编号。
    """
    if not content:
        return []
    out: List[dict] = []
    for m in _HIST_RULE_PAT.finditer(content):
        text = m.group(1).strip()
        req_raw = m.group(0)[len(m.group(1))+1:].strip()  # "（敏捷需求...）"
        out.append({"text": text, "req_id": req_raw})
    return out


# ---------------------------------------------------------------------------
# 渲染：场景规则（自动区）正文
# ---------------------------------------------------------------------------
def render_scenario_rules_block(db, domain_code: str) -> str:
    """渲染某领域「场景规则（自动区）」的权威正文（按场景类别分组 + 来源指纹）。

    无规则时返回 ``_暂无场景规则_``（与既有自动区占位口径一致）。
    """
    rules = collect_rules(db, domain_code).get(domain_code, [])
    if not rules:
        return "_暂无场景规则_"

    by_cat: Dict[str, List[dict]] = {}
    for r in rules:
        by_cat.setdefault(r["category"], []).append(r)

    # 说明行不写入时间戳：否则每次沉淀都产生 diff，破坏幂等（同步主笔记会误判「有变更」）
    lines = [
        f"> 本区由系统自动维护 · 规则沉淀：共 **{len(rules)}** 条，"
        "来源为需求用户故事的业务规则，按场景类别智能归类。人工请勿直接编辑。",
        "",
    ]
    # 类别按条数降序、同条数按名称，保证渲染稳定（幂等）
    ordered = sorted(by_cat.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    for cat, items in ordered:
        lines.append(f"**{cat}规则（{len(items)}）**")
        lines.append("")
        for it in items:
            src = f"（{it['req_id']}）" if it["req_id"] else ""
            lines.append(
                f"- {it['text']} `{src}` <!-- rule:{it['fingerprint']} -->"
            )
        lines.append("")
    return "\n".join(lines).rstrip()


# ---------------------------------------------------------------------------
# 写入：把渲染结果落盘到主笔记
# ---------------------------------------------------------------------------
def _ensure_scenario_rules_section(content: str, body: str) -> str:
    """主笔记尚无 场景规则 自动区标记时，定位/新建「场景规则」章节并插入标记块。

    优先复用已存在的「场景规则」标题章节（business §4.2 / 其他模板若已有），
    否则在文末追加 ``## 场景规则（自动区）`` 章节。
    """
    block = _auto_block(RULE_BLOCK_KEY, body + "\n")
    lines = content.split("\n")
    heading_pat = re.compile(r"^(#{2,3})\s+(.*场景规则.*)$")
    for i, ln in enumerate(lines):
        m = heading_pat.match(ln.strip())
        if not m:
            continue
        level = len(m.group(1))
        # 找该章节结束位置（下一个同级或更高级标题，或文末）
        j = i + 1
        while j < len(lines):
            hm = re.match(r"^(#{1,6})\s+", lines[j].strip())
            if hm and len(hm.group(1)) <= level:
                break
            j += 1
        # 去掉该章节尾部空行后在末尾插入
        end = j
        while end > i + 1 and not lines[end - 1].strip():
            end -= 1
        new_lines = lines[:end] + ["", block] + lines[end:]
        return "\n".join(new_lines)

    tail = content.rstrip("\n")
    return f"{tail}\n\n## 场景规则（自动区）\n\n> 自动区：由规则沉淀自动写入，人工请勿直接编辑。\n\n{block}\n"


def sediment_rules(db, domain_codes: Optional[List[str]] = None) -> dict:
    """把自动识别的规则智能归类并沉淀到对应主笔记的「场景规则（自动区）」。

    :param domain_codes: 指定领域；为空则沉淀所有存在候选规则的领域。
    :return: {total, success_count, results: [{domain_code, domain_name, rules, action, error}]}
    """
    buckets = collect_rules(db, domain_code=None)
    targets = [c for c in (domain_codes or sorted(buckets.keys())) if c in buckets]

    results: List[dict] = []
    for code in targets:
        domain = db.query(PmwbBusinessDomain).filter(
            PmwbBusinessDomain.domain_code == code
        ).first()
        item = (
            db.query(PmwbKnowledgeItem)
            .filter(PmwbKnowledgeItem.domain_code == code)
            .filter(PmwbKnowledgeItem.note_type == "main")
            .first()
        )
        if not item or not item.obsidian_path:
            results.append({
                "domain_code": code,
                "domain_name": domain.domain_name if domain else code,
                "rules": len(buckets.get(code, [])),
                "action": "skipped",
                "success": False,
                "error": "该领域无主笔记，请先一键同步创建主笔记",
            })
            continue

        content = read_markdown(item.obsidian_path) or ""
        body = render_scenario_rules_block(db, code)
        # upsert：已有自动区块则原地替换（并收敛历史重复块），否则定位/新建「场景规则」章节
        new_content = _upsert_auto_block(content, RULE_BLOCK_KEY, body)

        if new_content == content:
            results.append({
                "domain_code": code,
                "domain_name": domain.domain_name if domain else code,
                "rules": len(buckets.get(code, [])),
                "action": "unchanged",
                "success": True,
            })
            continue

        # 用户/系统主动触发的沉淀，绕过 5 分钟写保护窗口，避免「点了没生效」
        write_markdown(item.obsidian_path, new_content, protect_if_modified=False)
        results.append({
            "domain_code": code,
            "domain_name": domain.domain_name if domain else code,
            "rules": len(buckets.get(code, [])),
            "action": "written",
            "success": True,
            "obsidian_path": item.obsidian_path,
        })

    return {
        "total": len(results),
        "success_count": sum(1 for r in results if r.get("success")),
        "results": results,
    }


# ---------------------------------------------------------------------------
# 查询：待沉淀规则候选（供前端规则沉淀面板）
# ---------------------------------------------------------------------------
def scan_rule_candidates(db, domain_code: Optional[str] = None) -> dict:
    """扫描自动识别到的规则，按领域聚合，并标注每条是否已沉淀。

    返回 {total_rules, total_pending, domain_count, domains: [...]}。
    """
    buckets = collect_rules(db, domain_code=domain_code)
    # 已沉淀指纹按领域读取主笔记正文
    fp_by_domain: Dict[str, Set[str]] = {}
    for code in buckets.keys():
        item = (
            db.query(PmwbKnowledgeItem)
            .filter(PmwbKnowledgeItem.domain_code == code)
            .filter(PmwbKnowledgeItem.note_type == "main")
            .first()
        )
        fp_by_domain[code] = sedimented_fingerprints(
            read_markdown(item.obsidian_path) if item and item.obsidian_path else ""
        )

    domains_out = []
    total_rules = 0
    total_pending = 0
    for code, rules in sorted(buckets.items()):
        domain = db.query(PmwbBusinessDomain).filter(
            PmwbBusinessDomain.domain_code == code
        ).first()
        item = (
            db.query(PmwbKnowledgeItem)
            .filter(PmwbKnowledgeItem.domain_code == code)
            .filter(PmwbKnowledgeItem.note_type == "main")
            .first()
        )
        done = fp_by_domain.get(code, set())
        cat_counter: Dict[str, int] = {}
        pending_n = 0
        rule_rows = []
        for r in rules:
            sedimented = r["fingerprint"] in done
            if not sedimented:
                pending_n += 1
                cat_counter[r["category"]] = cat_counter.get(r["category"], 0) + 1
            rule_rows.append({
                "fingerprint": r["fingerprint"],
                "text": r["text"],
                "category": r["category"],
                "req_id": r["req_id"],
                "req_name": r["req_name"],
                "story_title": r["story_title"],
                "sedimented": sedimented,
            })
        total_rules += len(rules)
        total_pending += pending_n
        domains_out.append({
            "domain_code": code,
            "domain_name": domain.domain_name if domain else code,
            "domain_group": domain.domain_group if domain else "通用",
            "has_main_note": bool(item and item.obsidian_path),
            "total": len(rules),
            "pending": pending_n,
            "categories": [
                {"name": k, "count": v}
                for k, v in sorted(cat_counter.items(), key=lambda kv: (-kv[1], kv[0]))
            ],
            "rules": rule_rows,
        })

    return {
        "total_rules": total_rules,
        "total_pending": total_pending,
        "domain_count": len(domains_out),
        "domains": sorted(domains_out, key=lambda d: (-d["pending"], d["domain_name"])),
    }


def migrate_historical_rules(db, domain_code: Optional[str] = None) -> dict:
    """扫描并迁移历史规则（有内容但缺 fingerprint 标记）。

    返回 {migrated_count, results: [{domain_code, domain_name, migrated, status}]}
    """
    buckets = collect_rules(db, domain_code=domain_code)
    all_codes = set(buckets.keys())

    # 额外扫描主笔记中可能存在的历史规则（不在 DB 规则源中）
    from db.models import PmwbKnowledgeItem
    for item in (
        db.query(PmwbKnowledgeItem)
        .filter(PmwbKnowledgeItem.note_type == "main")
        .filter(PmwbKnowledgeItem.domain_code.isnot(None))
        .all()
    ):
        all_codes.add(item.domain_code)

    results: List[dict] = []
    migrated_count = 0
    for code in sorted(all_codes):
        item = (
            db.query(PmwbKnowledgeItem)
            .filter(PmwbKnowledgeItem.domain_code == code)
            .filter(PmwbKnowledgeItem.note_type == "main")
            .first()
        )
        if not item or not item.obsidian_path:
            continue
        content = read_markdown(item.obsidian_path) or ""
        auto_begin = f"<!-- PMWB:AUTO:BEGIN key=scenario_rules -->"
        auto_end = f"<!-- PMWB:AUTO:END key=scenario_rules -->"
        if auto_begin not in content or auto_end not in content:
            continue
        auto_start = content.find(auto_begin)
        auto_end_pos = content.find(auto_end) + len(auto_end)
        auto_content = content[auto_start:auto_end_pos]

        hist = scan_historical_rules(auto_content)
        if not hist:
            continue

        # 构建迁移后的规则内容（合并 DB 规则 + 历史规则，加指纹）
        db_rules = collect_rules(db, domain_code=code).get(code, [])
        existing_fps = sedimented_fingerprints(auto_content)

        # 去重：按 req_id + text 匹配
        db_by_req_text: Dict[str, dict] = {}
        for r in db_rules:
            key = f"{r['req_id']}|{r['text']}"
            db_by_req_text[key] = r

        new_hist_rules = []
        for h in hist:
            key = f"{h['req_id']}|{h['text']}"
            if key in db_by_req_text:
                continue  # DB 已有，跳过
            # 找 story_id（按 req_id 匹配）
            matching = [r for r in db_rules if r.get('req_id') == h['req_id']]
            if matching:
                story_id = matching[0]['story_id']
                idx = len([f for f in existing_fps if f.startswith(f"story-{story_id}-")])
            else:
                story_id = 0
                idx = 0
            new_hist_rules.append({
                "text": h["text"],
                "category": classify_rule(h["text"]),
                "req_id": h["req_id"],
                "fingerprint": f"story-{story_id}-{idx}",
            })
            existing_fps.add(f"story-{story_id}-{idx}")

        if not new_hist_rules:
            continue

        # 重新渲染场景规则块
        all_merged = db_rules + new_hist_rules
        # 按 req_id + text 去重（保持 DB 规则优先）
        seen: Set[str] = set()
        unique_rules: List[dict] = []
        for r in all_merged:
            k = f"{r['req_id']}|{r['text']}"
            if k in seen:
                continue
            seen.add(k)
            unique_rules.append(r)

        body = render_scenario_rules_block_rebuilt(unique_rules)
        new_content = _upsert_auto_block(content, RULE_BLOCK_KEY, body)

        if new_content == content:
            results.append({
                "domain_code": code,
                "domain_name": item.domain_name if hasattr(item, 'domain_name') else code,
                "migrated": 0,
                "status": "unchanged",
            })
            continue

        write_markdown(item.obsidian_path, new_content, protect_if_modified=False)
        migrated_count += len(new_hist_rules)
        results.append({
            "domain_code": code,
            "domain_name": item.domain_name if hasattr(item, 'domain_name') else code,
            "migrated": len(new_hist_rules),
            "status": "written",
        })

    return {
        "total_migrated": migrated_count,
        "results": results,
    }


def render_scenario_rules_block_rebuilt(rules: List[dict]) -> str:
    """用预收集的规则列表渲染场景规则正文（供迁移使用）。"""
    if not rules:
        return "_暂无场景规则_"
    by_cat: Dict[str, List[dict]] = {}
    for r in rules:
        by_cat.setdefault(r["category"], []).append(r)
    lines = [
        "> 本区由系统自动维护 · 规则沉淀：共 **{0}** 条，来源为需求用户故事的业务规则，按场景类别智能归类。人工请勿直接编辑。".format(len(rules)),
        "",
    ]
    ordered = sorted(by_cat.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    for cat, items in ordered:
        lines.append(f"**{cat}规则（{len(items)}）**")
        lines.append("")
        for it in items:
            src = f"（{it['req_id']}）" if it.get("req_id") else ""
            fp = it.get("fingerprint", "")
            lines.append(f"- {it['text']} `{src}` <!-- rule:{fp} -->")
        lines.append("")
    return "\n".join(lines).rstrip()
