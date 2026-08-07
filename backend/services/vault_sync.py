"""Obsidian Vault → PMWB 知识索引 反向同步服务。

职责：
- 仅扫描「业务领域字典」（pmwb_business_domain）中 enabled 且配置了 vault_path 的领域目录，
  把范围严格限制在用户关注的政企业务知识库（重点关注商客业务），不再全量扫描整个 Vault。
- 对每个扫描到的 .md 笔记，按「文件名 + 标题」匹配该领域下二级细分业务的 match_keywords，
  归入最具体的业务领域（domain_code），否则归入其父领域。
- 与已索引的 obsidian_path 对比，新增未被索引的笔记。

设计原则：业务领域字典是知识同步范围的唯一数据源，用户通过「业务知识维度管理」增删改领域
即可控制知识库拉取哪些笔记，从根本上避免「所有笔记都被带出来」。
"""

import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from core.config import settings
from db.models import PmwbBusinessDomain, PmwbKnowledgeItem
from utils.obsidian import get_vault_path, parse_frontmatter, parse_title


def _gen_item_id() -> str:
    return f"KN{uuid.uuid4().hex[:8].upper()}"


def _parse_keywords(raw: Optional[str]) -> List[str]:
    """把逗号/空格分隔的关键词字符串拆成小写列表。"""
    if not raw:
        return []
    return [k.strip().lower() for k in re.split(r"[,，\s]+", raw) if k.strip()]


def _build_scan_domains(db) -> List[PmwbBusinessDomain]:
    """取出 enabled 且配置了 vault_path 的业务领域，并跳过「路径是其它【真实存在】领域子目录」的父领域
    （避免重复扫描：例如扫描 commercial-group 的 商客业务 目录即可，不必再扫其 enterprise-group 父目录）。

    注意：只跳过那些「子目录确实存在、会被实际扫描」的父领域。若子领域的 vault_path 仅是配置值但目录
    并不存在（如商客业务下的细分业务是扁平 .md 文件而非子目录），则不跳过父领域，否则父目录的笔记会漏扫。
    """
    vault = get_vault_path().resolve()
    domains = (
        db.query(PmwbBusinessDomain)
        .filter(
            PmwbBusinessDomain.enabled == True,  # noqa: E712
            PmwbBusinessDomain.vault_path.isnot(None),
            PmwbBusinessDomain.vault_path != "",
        )
        .all()
    )
    paths = [d.vault_path.rstrip("/\\") for d in domains]
    scan = []
    for d in domains:
        vp = d.vault_path.rstrip("/\\")
        is_parent_of_other = any(
            other != vp
            and other.startswith(vp + "/")
            and (vault / other).is_dir()
            for other in paths
        )
        if not is_parent_of_other:
            scan.append(d)
    return scan


def _classify_domain(
    rel_path: str,
    title: str,
    domain: PmwbBusinessDomain,
    children_kw: Dict[str, List[Tuple[str, List[str]]]],
    code_info: Dict[str, Tuple[str, str]],
) -> str:
    """根据文件名 + 标题匹配该领域下二级细分业务的 match_keywords，命中则返回子领域编码，否则返回当前领域编码。"""
    haystack = (os.path.basename(rel_path) + " " + (title or "")).lower()
    for child_code, kws in children_kw.get(domain.domain_code, []):
        for kw in kws:
            if kw and kw in haystack:
                return child_code
    return domain.domain_code


def sync_from_vault(
    db,
    dirs: List[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """从 Obsidian Vault 同步笔记到知识索引（范围严格受业务领域字典约束）。

    参数：
        db: SQLAlchemy Session
        dirs: 已废弃，保留签名兼容；实际扫描范围由业务领域字典的 vault_path 决定。
        dry_run: True 时只统计，不实际写入

    返回：{
        "scanned": 扫描到的文件数,
        "new_indexed": 新增索引数,
        "skipped_existing": 已有索引跳过数,
        "synced_files": [新增的文件列表],
    }
    """
    vault = get_vault_path().resolve()

    domains = _build_scan_domains(db)
    # 二级细分业务关键词表：父领域编码 -> [(子领域编码, [关键词])]
    children_kw: Dict[str, List[Tuple[str, List[str]]]] = {}
    for d in domains:
        if d.parent_id:
            parent = d.parent
            if parent and parent.domain_code:
                children_kw.setdefault(parent.domain_code, []).append(
                    (d.domain_code, _parse_keywords(d.match_keywords))
                )
    # 领域编码 -> (业务大类, 业务名)，用于填充 category / sub_category
    code_info: Dict[str, Tuple[str, str]] = {
        d.domain_code: (d.domain_group, d.domain_name) for d in domains
    }

    # 1. 获取所有已索引的 obsidian_path
    existing_paths: Set[str] = set()
    for row in db.query(PmwbKnowledgeItem.obsidian_path).all():
        if row[0]:
            existing_paths.add(row[0].replace("\\", "/"))

    # 2. 扫描受限范围内的 Vault 目录
    scanned_files: List[Dict] = []
    for domain in domains:
        root = vault / domain.vault_path
        if not root.exists() or not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            # 跳过隐藏目录和附件目录
            dirnames[:] = [
                d
                for d in dirnames
                if not d.startswith(".")
                and d.lower() not in ("attachment", "attachments", "assets")
            ]
            for fn in filenames:
                if not fn.lower().endswith(".md"):
                    continue
                full_path = Path(dirpath) / fn
                rel = str(full_path.relative_to(vault)).replace("\\", "/")
                if rel in existing_paths:
                    continue
                try:
                    text = full_path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    text = ""
                title = parse_title(text) or fn[:-3]
                fm = parse_frontmatter(text)

                domain_code = _classify_domain(
                    rel, title, domain, children_kw, code_info
                )
                grp, name = code_info.get(domain_code, (domain.domain_group, domain.domain_name))

                scanned_files.append({
                    "path": rel,
                    "title": title,
                    "tags": fm.get("tags", ""),
                    "created_date": fm.get("created_date", ""),
                    "domain_code": domain_code,
                    "category": grp or "业务知识",
                    "sub_category": name,
                })

    # 3. 创建索引条目
    synced = []
    if not dry_run:
        for f in scanned_files:
            try:
                full_text = (vault / f["path"]).read_text(encoding="utf-8", errors="ignore")
            except Exception:
                full_text = ""
            body = re.sub(r"^---\s*\n.*?\n---\s*\n", "", full_text, flags=re.DOTALL)
            body_lines = [
                l.strip()
                for l in body.split("\n")
                if l.strip() and not l.strip().startswith("#")
            ]
            summary = " ".join(body_lines[:3])[:200] if body_lines else ""

            item = PmwbKnowledgeItem(
                item_id=_gen_item_id(),
                title=f["title"],
                category=f["category"],
                sub_category=f["sub_category"],
                tags=f["tags"],
                obsidian_path=f["path"],
                source_type="vault_sync",
                source_id=None,
                domain_code=f["domain_code"],
                summary=summary,
            )
            db.add(item)
            synced.append(f["path"])

        if synced:
            db.commit()

    return {
        "scanned": len(scanned_files) + len(existing_paths),
        "new_indexed": len(scanned_files) if dry_run else len(synced),
        "skipped_existing": len(existing_paths),
        "synced_files": synced if not dry_run else [f["path"] for f in scanned_files],
    }
