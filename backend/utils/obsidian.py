import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

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
