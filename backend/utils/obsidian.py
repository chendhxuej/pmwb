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


def delete_markdown(relative_path: str) -> bool:
    """删除 Obsidian Vault 中指定相对路径的笔记，返回是否实际删除。"""
    if not relative_path:
        return False
    vault = get_vault_path()
    file_path = vault / relative_path
    if file_path.exists():
        file_path.unlink()
        return True
    return False


def force_write_markdown(relative_path: str, content: str) -> str:
    """强制覆盖写入 Markdown（用于重新生成纪要/需求等幂等更新场景）。"""
    return write_markdown(relative_path, content)


def _split_frontmatter(content: str):
    """拆分 Markdown 为 (frontmatter_dict, frontmatter_raw, body)。

    frontmatter_dict: 解析后的键值对（支持简单标量与列表）。
    frontmatter_raw: 原始 frontmatter 文本（含 --- 边界），无则为空串。
    body: 正文（不含 frontmatter）。
    """
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", content, re.DOTALL)
    if not m:
        return {}, "", content
    raw = m.group(1)
    body = m.group(2)
    fm = {}
    for line in raw.split("\n"):
        if not line.strip() or line.strip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        # 列表值如 [a, b] 或 ["a", "b"]
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            items = [v.strip().strip('"').strip("'") for v in inner.split(",") if v.strip()]
            fm[key] = items
        else:
            fm[key] = value.strip('"').strip("'")
    return fm, f"---\n{raw}\n--", body


def read_frontmatter(relative_path: str) -> Dict[str, object]:
    """读取 Obsidian 笔记的 frontmatter（支持标量与 YAML 数组字段），无则返回空 dict。"""
    content = read_markdown(relative_path)
    if content is None:
        return {}
    fm, _, _ = _split_frontmatter(content)
    return fm


def write_frontmatter(relative_path: str, data: Dict[str, object]) -> str:
    """重写 Obsidian 笔记的 frontmatter（保留正文），支持标量与数组字段，返回完整路径。

    注意：整块重建 frontmatter，调用方需传入完整字段集；
    如需只改个别字段请用 set_frontmatter_value / append_frontmatter_list / remove_frontmatter_list。
    """
    content = read_markdown(relative_path)
    if content is None:
        content = ""
    _, _, body = _split_frontmatter(content)
    lines = ["---"]
    for k, v in data.items():
        if isinstance(v, list):
            if not v:
                lines.append(f"{k}: []")
            else:
                lines.append(f'{k}: [{ ", ".join(str(x) for x in v)}]')
        elif v is None:
            lines.append(f"{k}:")
        else:
            lines.append(f'{k}: "{v}"' if isinstance(v, str) and ("," in v or " " in v or not v) else f"{k}: {v}")
    lines.append("---")
    new_content = "\n".join(lines) + "\n\n" + body.lstrip("\n")
    return write_markdown(relative_path, new_content)


def append_or_replace_section(content: str, heading: str, body: str) -> str:
    """按标题替换或追加正文章节（`## heading`），返回新内容。

    body 为纯正文（不含标题行）；与 replace_section 行为一致，提供语义化别名。
    """
    return replace_section(content, heading, body)


def set_frontmatter_value(content: str, key: str, value) -> str:
    """设置/新增 frontmatter 中某个标量字段，返回新内容。"""
    fm, raw, body = _split_frontmatter(content)
    fm[key] = value
    lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, list):
            if not v:
                lines.append(f"{k}: []")
            else:
                lines.append(f'{k}: [{", ".join(v)}]')
        else:
            lines.append(f'{k}: "{v}"' if isinstance(v, str) and ("," in v or " " in v or not v) else f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines) + "\n" + body


def append_frontmatter_list(content: str, key: str, value: str) -> str:
    """向 frontmatter 的列表字段追加一项（去重），返回新内容。"""
    fm, raw, body = _split_frontmatter(content)
    existing = fm.get(key)
    if isinstance(existing, str):
        existing = [existing] if existing else []
    elif existing is None:
        existing = []
    if value not in existing:
        existing.append(value)
    fm[key] = existing
    lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, list):
            if not v:
                lines.append(f"{k}: []")
            else:
                lines.append(f'{k}: [{", ".join(v)}]')
        else:
            lines.append(f'{k}: "{v}"' if isinstance(v, str) and ("," in v or " " in v or not v) else f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines) + "\n" + body


def remove_frontmatter_list(content: str, key: str, value: str) -> str:
    """从 frontmatter 列表字段移除一项，返回新内容。"""
    fm, raw, body = _split_frontmatter(content)
    existing = fm.get(key)
    if isinstance(existing, str):
        existing = [existing]
    elif existing is None:
        return content
    existing = [x for x in existing if x != value]
    fm[key] = existing
    lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, list):
            if not v:
                lines.append(f"{k}: []")
            else:
                lines.append(f'{k}: [{", ".join(v)}]')
        else:
            lines.append(f'{k}: "{v}"' if isinstance(v, str) and ("," in v or " " in v or not v) else f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines) + "\n" + body


def replace_section(content: str, heading: str, new_body: str) -> str:
    """替换或追加一个名为 `## heading` 的章节（保留其余内容）。

    new_body 不含标题行，调用方传入纯正文（可多行）。
    """
    lines = content.split("\n")
    new_lines = []
    i = 0
    replaced = False
    n = len(lines)
    heading_pat = re.compile(r"^##\s+" + re.escape(heading) + r"\s*$")
    while i < n:
        line = lines[i]
        if heading_pat.match(line):
            replaced = True
            new_lines.append(f"## {heading}")
            new_lines.append("")
            # 跳过直到下一个同级或更高级标题
            j = i + 1
            while j < n and not re.match(r"^##\s+", lines[j]) and not re.match(r"^#\s+", lines[j]):
                j += 1
            # 插入新正文
            for bl in new_body.strip("\n").split("\n"):
                new_lines.append(bl)
            new_lines.append("")
            i = j
            continue
        new_lines.append(line)
        i += 1
    if not replaced:
        new_lines.append("")
        new_lines.append(f"## {heading}")
        new_lines.append("")
        for bl in new_body.strip("\n").split("\n"):
            new_lines.append(bl)
        new_lines.append("")
    return "\n".join(new_lines).rstrip("\n") + "\n"


# ---------------------------------------------------------------------------
# kc4-2：主笔记「自动区」标记块（人工区零覆盖的核心保障）
# ---------------------------------------------------------------------------
# 设计要点（相比按标题名替换更科学、更安全）：
# 1. 自动内容一律夹在 <!-- PMWB:AUTO:BEGIN key=xxx --> / <!-- PMWB:AUTO:END key=xxx --> 之间；
# 2. 系统只重写标记之间的内容，标记之外（人工撰写的概述/SOP/通用规则）永不触碰；
# 3. 幂等：每次同步为「整块替换」，不会重复追加；
# 4. 标记在 Obsidian 中渲染为注释（不可见），但源码可见，用户明确知道哪块由系统维护；
# 5. 章节改名/挪位不影响（以 key 为契约，不依赖标题文字）。

AUTO_BEGIN_TPL = "<!-- PMWB:AUTO:BEGIN key={key} -->"
AUTO_END_TPL = "<!-- PMWB:AUTO:END key={key} -->"


def _auto_block_pattern(key: str) -> "re.Pattern":
    return re.compile(
        re.escape(AUTO_BEGIN_TPL.format(key=key)) + r".*?" + re.escape(AUTO_END_TPL.format(key=key)),
        re.DOTALL,
    )


def render_auto_block(key: str, body: str) -> str:
    """渲染一个带标记的自动区块。"""
    inner = (body or "").strip("\n")
    return "\n".join(
        [
            AUTO_BEGIN_TPL.format(key=key),
            inner if inner else "_暂无数据_",
            AUTO_END_TPL.format(key=key),
        ]
    )


def has_auto_block(content: str, key: str) -> bool:
    return bool(_auto_block_pattern(key).search(content or ""))


def upsert_auto_block(
    content: str,
    key: str,
    body: str,
    anchor_heading: Optional[str] = None,
) -> str:
    """写入/更新自动区块，返回新内容。**只改标记之间的内容，人工区零覆盖。**

    - 已存在同 key 标记块 → 原地整块替换（幂等）；
    - 不存在且给了 anchor_heading（`## heading` 文本）→ 追加到该章节末尾（章节内人工内容保留）；
    - 不存在且无 anchor_heading（或章节不存在）→ 追加到文末新建 `## anchor_heading` 章节。
    """
    content = content or ""
    block = render_auto_block(key, body)
    pat = _auto_block_pattern(key)
    if pat.search(content):
        return pat.sub(lambda _m: block, content, count=1)

    if not anchor_heading:
        return content.rstrip("\n") + "\n\n" + block + "\n"

    lines = content.split("\n")
    heading_pat = re.compile(r"^##\s+" + re.escape(anchor_heading) + r"\s*$")
    n = len(lines)
    for i, line in enumerate(lines):
        if heading_pat.match(line):
            # 找到该章节结束位置（下一个同级/更高级标题前）
            j = i + 1
            while j < n and not re.match(r"^##\s+", lines[j]) and not re.match(r"^#\s+", lines[j]):
                j += 1
            # 去掉章节尾部空行后插入区块
            k = j
            while k > i + 1 and not lines[k - 1].strip():
                k -= 1
            new_lines = lines[:k] + ["", block, ""] + lines[j:]
            return "\n".join(new_lines).rstrip("\n") + "\n"

    # 章节不存在：新建章节承载自动区块
    return (
        content.rstrip("\n") + "\n\n" + f"## {anchor_heading}" + "\n\n" + block + "\n"
    )
