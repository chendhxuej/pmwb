import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from core.config import settings


def get_vault_path() -> Path:
    return Path(settings.OBSIDIAN_VAULT_PATH)


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def sanitize_filename(name: str) -> str:
    """清理文件名中的非法字符。"""
    return re.sub(r'[\\/:*?"<>|]', "_", name)


def write_markdown(relative_path: str, content: str) -> str:
    """写入 Markdown 文件到 Obsidian Vault，返回完整路径。"""
    vault = get_vault_path()
    file_path = vault / relative_path
    ensure_dir(file_path.parent)
    file_path.write_text(content, encoding="utf-8")
    return str(file_path)


def read_markdown(relative_path: str) -> Optional[str]:
    vault = get_vault_path()
    file_path = vault / relative_path
    if not file_path.exists():
        return None
    return file_path.read_text(encoding="utf-8")


def parse_title(markdown: str) -> str:
    """取第一个一级标题作为标题，否则返回空串。"""
    for line in (markdown or "").splitlines():
        m = re.match(r"^#\s+(.+)$", line.strip())
        if m:
            return m.group(1).strip()
    return ""


def list_notes(folders: List[str]) -> List[Dict[str, str]]:
    """列出 vault 指定目录下所有 .md 笔记，返回 {path,title,folder,mtime}。"""
    vault = get_vault_path().resolve()
    results = []
    seen = set()
    for folder in folders or []:
        root = vault / folder
        if not root.exists() or not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            # 跳过隐藏目录与附件目录
            dirnames[:] = [
                d
                for d in dirnames
                if not d.startswith(".")
                and d.lower() not in ("attachment", "attachments")
            ]
            for fn in filenames:
                if not fn.lower().endswith(".md"):
                    continue
                full = Path(dirpath) / fn
                rel = str(full.relative_to(vault)).replace("\\", "/")
                if rel in seen:
                    continue
                seen.add(rel)
                try:
                    text = full.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    text = ""
                title = parse_title(text) or fn[:-3]
                results.append(
                    {
                        "path": rel,
                        "title": title,
                        "folder": folder,
                        "mtime": full.stat().st_mtime,
                    }
                )
    results.sort(key=lambda x: (x["folder"], x["path"]))
    return results


def write_markdown_safe(relative_path: str, content: str) -> str:
    """写回 Obsidian 笔记，强制校验路径位于 vault 内，杜绝路径穿越。"""
    vault = get_vault_path().resolve()
    full = (vault / relative_path).resolve()
    if full != vault and vault not in full.parents:
        raise ValueError("路径越界：必须位于 Obsidian vault 内")
    ensure_dir(full.parent)
    full.write_text(content, encoding="utf-8")
    return str(full)


def parse_frontmatter(content: str) -> Dict[str, str]:
    """简单解析 Markdown 文件中的 YAML frontmatter。"""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if not match:
        return {}

    frontmatter = match.group(1)
    result = {}
    for line in frontmatter.split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            result[key.strip()] = value.strip()
    return result


def build_frontmatter(data: Dict[str, str]) -> str:
    """构造 YAML frontmatter。"""
    lines = ["---"]
    for key, value in data.items():
        lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines)


def format_datetime(dt: Optional[datetime] = None, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    return (dt or datetime.now()).strftime(fmt)
