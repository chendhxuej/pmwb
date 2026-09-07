"""业务资料库在线预览引擎。

按扩展名分支成 8 类处理，统一返回：
    {"mode": "html" | "text" | "stream" | "unsupported", ...}

- html   : 已渲染好的 HTML 片段，前端直接 v-html（xlsx / docx / pptx / zip）
- text   : 纯文本内容，前端自行渲染（txt / md）
- stream : 交给 FileResponse 原样输出（pdf / 图片 / html）
- unsupported : 不支持预览，前端只给下载按钮

性能保护：所有解析都设上限（行数/列数/页数/条目数），避免大文件把请求打挂。
"""

from __future__ import annotations

import base64
import csv
import html
import io
import os
import zipfile
from datetime import date, datetime
from typing import Any, Optional

from utils import file_storage as fs

# ---- 性能保护上限 ----
XLSX_MAX_ROWS = 300
XLSX_MAX_COLS = 30
XLSX_MAX_SHEETS = 10
PPTX_MAX_SLIDES = 80
PPTX_MAX_IMAGE_MB = 5
ZIP_MAX_ENTRIES = 500
DOCX_MAX_BYTES = 40 * 1024 * 1024
TEXT_MAX_BYTES = 2 * 1024 * 1024

_STREAM_MIME = {
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "bmp": "image/bmp",
    "webp": "image/webp",
    "svg": "image/svg+xml",
    "htm": "text/html; charset=utf-8",
    "html": "text/html; charset=utf-8",
}

_CSS = """
.pv-wrap{font-family:'PingFang SC','Microsoft YaHei',system-ui,sans-serif;color:#0f172a;
  font-size:13px;line-height:1.7;padding:4px 2px}
.pv-note{background:#fff7e6;border:1px solid #ffd591;border-radius:8px;padding:8px 12px;
  margin-bottom:12px;color:#854f0b;font-size:12px}
.pv-table-scroll{overflow:auto;border:1px solid #e4e9f0;border-radius:10px}
.pv-table{border-collapse:collapse;width:100%;font-size:12px;white-space:nowrap}
.pv-table th,.pv-table td{border:1px solid #e4e9f0;padding:6px 10px;text-align:left}
.pv-table thead th{background:#f3f5f9;font-weight:600;position:sticky;top:0}
.pv-table tbody tr:nth-child(even){background:#fafbfd}
.pv-sheet{margin-bottom:18px}
.pv-sheet-name{font-weight:600;margin-bottom:6px;color:#2f6fed}
.pv-doc img{max-width:100%;height:auto}
.pv-doc table{border-collapse:collapse;margin:10px 0}
.pv-doc td,.pv-doc th{border:1px solid #e4e9f0;padding:6px 10px}
.pv-slide{border:1px solid #e4e9f0;border-radius:12px;padding:16px 18px;margin-bottom:14px;
  background:#fff;box-shadow:0 1px 3px rgba(15,23,42,.06)}
.pv-slide-no{display:inline-block;min-width:26px;height:22px;line-height:22px;text-align:center;
  background:#eaf1fe;color:#2f6fed;border-radius:6px;font-size:12px;font-weight:600;margin-right:8px}
.pv-slide-title{font-size:14px;font-weight:600;margin-bottom:8px}
.pv-para{margin:3px 0;padding-left:14px;position:relative}
.pv-para::before{content:'';position:absolute;left:2px;top:9px;width:4px;height:4px;
  border-radius:50%;background:#94a3b8}
.pv-para.pv-lv0{padding-left:0}
.pv-para.pv-lv0::before{display:none}
.pv-slide img{max-width:100%;height:auto;border:1px solid #e4e9f0;border-radius:8px;margin:6px 0}
.pv-zip{list-style:none;padding:0;margin:0}
.pv-zip li{display:flex;align-items:center;gap:10px;padding:6px 10px;border-bottom:1px solid #eff2f8;font-size:12px}
.pv-zip li:hover{background:#fafbfd}
.pv-zip .pv-zn{flex:1;word-break:break-all}
.pv-zip .pv-zs{color:#64748b;font-variant-numeric:tabular-nums;white-space:nowrap}
.pv-zip .pv-zr{color:#94a3b8;width:52px;text-align:right;font-variant-numeric:tabular-nums}
.pv-dir{color:#2f6fed;font-weight:500}
.pv-meta{color:#64748b;font-size:12px;margin-bottom:10px}
"""


def _wrap(inner: str, note: str = "") -> str:
    note_html = f'<div class="pv-note">{html.escape(note)}</div>' if note else ""
    return f'<style>{_CSS}</style><div class="pv-wrap">{note_html}{inner}</div>'


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


# ---------------------------------------------------------------- xlsx / csv
def _preview_xlsx(full: str) -> str:
    import openpyxl

    wb = openpyxl.load_workbook(full, data_only=True, read_only=True)
    parts: list[str] = []
    truncated_sheets = 0
    try:
        for idx, ws in enumerate(wb.worksheets):
            if idx >= XLSX_MAX_SHEETS:
                truncated_sheets += 1
                continue
            rows: list[list[str]] = []
            for r_idx, row in enumerate(ws.iter_rows(values_only=True)):
                if r_idx >= XLSX_MAX_ROWS:
                    break
                rows.append([_cell(c) for c in row[: XLSX_MAX_COLS]])
            total_rows = ws.max_row or 0
            total_cols = ws.min_column and (ws.max_column or 0) or 0

            if not rows:
                parts.append(
                    f'<div class="pv-sheet"><div class="pv-sheet-name">'
                    f'{html.escape(ws.title)}</div><div class="pv-meta">（空工作表）</div></div>'
                )
                continue

            head = "".join(f"<th>{html.escape(str(c) or chr(65 + i))}</th>" for i, c in enumerate(rows[0]))
            body_rows = []
            for r in rows[1:]:
                tds = "".join(f"<td>{html.escape(str(c))}</td>" for c in r)
                body_rows.append(f"<tr>{tds}</tr>")
            body = "".join(body_rows)

            cut = ""
            if total_rows > XLSX_MAX_ROWS:
                cut = f"<div class='pv-meta'>仅显示前 {XLSX_MAX_ROWS} 行（共 {total_rows} 行），完整内容请下载查看</div>"
            elif total_cols > XLSX_MAX_COLS:
                cut = f"<div class='pv-meta'>仅显示前 {XLSX_MAX_COLS} 列（共 {total_cols} 列），完整内容请下载查看</div>"

            parts.append(
                f'<div class="pv-sheet"><div class="pv-sheet-name">{html.escape(ws.title)}'
                f' <span class="pv-meta">（{total_rows} 行 × {total_cols} 列）</span></div>'
                f'<div class="pv-table-scroll"><table class="pv-table"><thead><tr>{head}</tr></thead>'
                f"<tbody>{body}</tbody></table></div>{cut}</div>"
            )
    finally:
        wb.close()

    if truncated_sheets:
        parts.append(f'<div class="pv-meta">另有 {truncated_sheets} 个工作表未显示</div>')
    return _wrap("".join(parts))


def _preview_csv(full: str) -> str:
    with open(full, "r", encoding="utf-8-sig", errors="replace", newline="") as f:
        reader = csv.reader(f)
        rows = [r[: XLSX_MAX_COLS] for i, r in enumerate(reader) if i < XLSX_MAX_ROWS]
    if not rows:
        return _wrap('<div class="pv-meta">（空文件）</div>')
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in rows[0])
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in r) + "</tr>" for r in rows[1:]
    )
    return _wrap(
        f'<div class="pv-sheet"><div class="pv-table-scroll"><table class="pv-table">'
        f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div></div>"
    )


# ---------------------------------------------------------------------- docx
def _preview_docx(full: str) -> str:
    import mammoth

    if os.path.getsize(full) > DOCX_MAX_BYTES:
        return _wrap('<div class="pv-meta">文件过大，已跳过在线预览，请下载后查看。</div>')
    with open(full, "rb") as f:
        result = mammoth.convert_to_html(f)
    body = result.value or ""
    messages = [m.message for m in result.messages][:5]
    note = "；".join(messages) if messages else ""
    return _wrap(f'<div class="pv-doc">{body}</div>', note)


# ---------------------------------------------------------------------- pptx
def _preview_pptx(full: str) -> str:
    from pptx import Presentation
    from pptx.util import Emu

    prs = Presentation(full)
    slides = list(prs.slides)
    parts: list[str] = []

    for idx, slide in enumerate(slides[:PPTX_MAX_SLIDES]):
        blocks: list[str] = []
        title = ""
        try:
            if slide.shapes.title is not None:
                title = (slide.shapes.title.text or "").strip()
        except Exception:
            title = ""

        for shape in slide.shapes:
            # 文本
            if getattr(shape, "has_text_frame", False):
                for para in shape.text_frame.paragraphs:
                    text = "".join(r.text for r in para.runs).strip()
                    if not text:
                        continue
                    if title and text == title:
                        continue
                    level = getattr(para, "level", 0) or 0
                    blocks.append(
                        f'<p class="pv-para pv-lv{level}">{html.escape(text)}</p>'
                    )
            # 表格
            if getattr(shape, "has_table", False):
                rows_html = []
                for row in shape.table.rows:
                    tds = "".join(
                        f"<td>{html.escape((cell.text or '').strip())}</td>" for cell in row.cells
                    )
                    rows_html.append(f"<tr>{tds}</tr>")
                blocks.append(
                    f'<div class="pv-table-scroll"><table class="pv-table"><tbody>'
                    f'{"".join(rows_html)}</tbody></table></div>'
                )
            # 图片
            if shape.shape_type == 13 or getattr(shape, "image", None) is not None:
                try:
                    image = shape.image
                    blob = image.blob
                    if len(blob) <= PPTX_MAX_IMAGE_MB * 1024 * 1024:
                        b64 = base64.b64encode(blob).decode()
                        mime = image.content_type or "image/png"
                        blocks.append(f'<img src="data:{mime};base64,{b64}" alt="幻灯片图片"/>')
                except Exception:
                    blocks.append('<p class="pv-para">（图片读取失败）</p>')

        body = "".join(blocks) or '<p class="pv-meta">（本页无文本内容）</p>'
        head = f'<div class="pv-slide-title">{html.escape(title)}</div>' if title else ""
        parts.append(
            f'<div class="pv-slide"><div><span class="pv-slide-no">{idx + 1}</span>{head}</div>{body}</div>'
        )

    total = len(slides)
    tail = ""
    if total > PPTX_MAX_SLIDES:
        tail = f'<div class="pv-meta">仅显示前 {PPTX_MAX_SLIDES} 页（共 {total} 页）</div>'
    note = "简化预览：可查看全部文字、表格与图片，但不还原原文件的排版位置、动画与图表样式。排版以原文件为准。"
    return _wrap("".join(parts) + tail, note)


# ----------------------------------------------------------------------- zip
def _fix_zip_name(info: zipfile.ZipInfo) -> str:
    """修复 zip 中文文件名乱码（非 UTF-8 标志位时按 GBK 重新解码）。"""
    name = info.filename
    if info.flag_bits & 0x800:
        return name
    try:
        return name.encode("cp437").decode("gbk")
    except Exception:
        try:
            return name.encode("cp437").decode("utf-8")
        except Exception:
            return name


def _preview_zip(full: str) -> str:
    import zipfile as zf

    with zf.ZipFile(full) as z:
        infos = z.infolist()
        total = len(infos)
        items = []
        total_size = 0
        total_comp = 0
        for info in infos[:ZIP_MAX_ENTRIES]:
            name = _fix_zip_name(info)
            is_dir = name.endswith("/")
            size = info.file_size
            comp = info.compress_size
            if not is_dir:
                total_size += size
                total_comp += comp
            ratio = ""
            if not is_dir and size:
                ratio = f"{(1 - comp / size) * 100:.0f}%"
            cls = "pv-dir" if is_dir else ""
            items.append(
                f'<li><span class="pv-zn {cls}">{html.escape(name)}</span>'
                f'<span class="pv-zs">{fs.human_size(size) if not is_dir else ""}</span>'
                f'<span class="pv-zr">{ratio}</span></li>'
            )
    tail = ""
    if total > ZIP_MAX_ENTRIES:
        tail = f'<div class="pv-meta">仅显示前 {ZIP_MAX_ENTRIES} 项（共 {total} 项）</div>'
    overall = ""
    if total_size:
        overall = (
            f"共 {total} 项，原始大小 {fs.human_size(total_size)}，"
            f"压缩后 {fs.human_size(total_comp)}"
        )
    note = "压缩包仅列出文件清单，不解压缩内容。需要查看内部文件请先下载。"
    inner = (
        f'<div class="pv-meta">{html.escape(overall)}</div>'
        f'<ul class="pv-zip">{"".join(items)}</ul>{tail}'
    )
    return _wrap(inner, note)


# --------------------------------------------------------------------- 入口
def build_preview(storage_root: str, rel_path: str, *, file_ext_hint: Optional[str] = None) -> dict:
    """生成预览结果。文件不存在时抛出 FileNotFoundError 由调用方处理。"""
    full = fs.abs_path(storage_root, rel_path)
    if not os.path.isfile(full):
        raise FileNotFoundError(full)

    ext = (file_ext_hint or fs.file_ext(full)).lower()

    if ext in _STREAM_MIME:
        return {"mode": "stream", "media_type": _STREAM_MIME[ext], "ext": ext}

    if ext in ("xlsx", "xlsm"):
        return {"mode": "html", "html": _preview_xlsx(full), "ext": ext}
    if ext == "xls":
        return {
            "mode": "unsupported",
            "ext": ext,
            "reason": "旧版 .xls 格式不支持在线预览，请下载后查看，或另存为 .xlsx 再上传",
        }
    if ext == "csv":
        return {"mode": "html", "html": _preview_csv(full), "ext": ext}
    if ext == "docx":
        return {"mode": "html", "html": _preview_docx(full), "ext": ext}
    if ext == "doc":
        return {
            "mode": "unsupported",
            "ext": ext,
            "reason": "旧版 .doc 格式不支持在线预览，请下载后查看，或另存为 .docx 再上传",
        }
    if ext == "pptx":
        return {"mode": "html", "html": _preview_pptx(full), "ext": ext}
    if ext == "ppt":
        return {
            "mode": "unsupported",
            "ext": ext,
            "reason": "旧版 .ppt 格式不支持在线预览，请下载后查看，或另存为 .pptx 再上传",
        }
    if ext == "zip":
        return {"mode": "html", "html": _preview_zip(full), "ext": ext}
    if ext in ("rar", "7z", "tar", "gz"):
        return {
            "mode": "unsupported",
            "ext": ext,
            "reason": f".{ext} 压缩包不支持在线预览（仅支持 .zip），请下载后查看",
        }
    if ext in ("txt", "log", "sql", "json", "xml", "yaml", "yml", "ini", "py", "js", "css"):
        size = os.path.getsize(full)
        if size > TEXT_MAX_BYTES:
            return {"mode": "unsupported", "ext": ext, "reason": "文本文件过大，请下载后查看"}
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            return {"mode": "text", "text": f.read(), "ext": ext}
    if ext in ("md", "markdown"):
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            return {"mode": "text", "text": f.read(), "ext": ext, "markdown": True}

    return {
        "mode": "unsupported",
        "ext": ext,
        "reason": f".{ext or '未知'} 格式暂不支持在线预览，请下载后查看",
    }
