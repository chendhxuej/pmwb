"""产品圣经：Word(.docx) -> HTML 转换 + EMF 光栅化。

设计原则：
- 纯标准库解析 OOXML（zipfile + xml.etree），不依赖 python-docx，避免离线环境 pip 失败。
- EMF 矢量图用 ctypes 调 Windows GDI 光栅化为 BMP（浏览器原生支持 BMP），不依赖 pywin32 / Pillow。
- 输出的 HTML 复用前端 MarkdownRender（html:true），h2/h3 生成 TOC、表格横向滚动、搜索高亮均生效。
"""
from __future__ import annotations

import ctypes
import io
import os
import struct
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

# ---- OOXML 命名空间 ----
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"


def _q(ns: str, tag: str) -> str:
    return f"{{{ns}}}{tag}"


def _strip_ns(tag: str) -> str:
    return tag.split("}", 1)[-1]


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _style_outline_map(styles_root: ET.Element) -> dict:
    """styleId -> outlineLvl(int)，用于把段落样式还原成标题层级。"""
    mapping = {}
    for style in styles_root.iter(_q(W, "style")):
        sid = style.get(_q(W, "styleId"))
        if not sid:
            continue
        # outlineLvl 可能是 <w:style> 的直接子节点，也可能嵌套，用 iter 稳妥
        lvl = next(style.iter(_q(W, "outlineLvl")), None)
        if lvl is not None:
            try:
                mapping[sid] = int(lvl.get(_q(W, "val")))
            except (TypeError, ValueError):
                pass
    return mapping


def _run_text(run: ET.Element) -> str:
    """提取一个 w:r 的可见文本（含换行/制表），并包裹颜色样式。"""
    parts = []
    # 拼接所有 w:t
    txt = "".join(
        t.text or "" for t in run.iter(_q(W, "t"))
    )
    # w:tab / w:br / w:cr
    for br in run.iter(_q(W, "br")):
        txt += "\n"
    for _ in run.iter(_q(W, "tab")):
        txt += "\t"

    color = None
    rpr = run.find(_q(W, "rPr"))
    if rpr is not None:
        c = rpr.find(_q(W, "color"))
        if c is not None:
            val = (c.get(_q(W, "val")) or "").lower()
            if val and val not in ("auto", "000000"):
                color = "#" + val
    if color:
        return f'<span style="color:{color}">{_esc(txt)}</span>'
    return _esc(txt)


def _paragraph_html(p: ET.Element, outline_map: dict) -> str:
    """段落 -> <hN> 或 <p>。"""
    # 跳过域代码指令（目录 TOC 域等）
    text_parts = []
    style_id = None
    ppr = p.find(_q(W, "pPr"))
    if ppr is not None:
        style = ppr.find(_q(W, "pStyle"))
        if style is not None:
            style_id = style.get(_q(W, "val"))
        # 忽略目录域段落（instrText）
        if ppr.find(_q(W, "numPr")) is not None:
            pass
    # 收集文本（跳过 instrText）
    runs = p.findall(_q(W, "r"))
    has_field = any(r.find(_q(W, "fldChar")) is not None or r.find(_q(W, "instrText")) is not None for r in runs)
    body = "".join(_run_text(r) for r in runs)
    plain = "".join(t.text or "" for t in p.iter(_q(W, "t"))).strip()
    if has_field and not plain:
        return ""

    outline = outline_map.get(style_id) if style_id else None
    if outline is not None and outline <= 5:
        level = outline + 1  # outlineLvl 0 -> h1
        return f"<h{level}>{body}</h{level}>"
    # 空段落
    if not plain:
        return '<p style="margin:0.3em 0"></p>'
    return f"<p>{body}</p>"


def _extract_images(el: ET.Element, rels: dict, media_set: set) -> list:
    """提取元素内（含嵌套）的图片，返回 <img> HTML 列表并更新 media_set。"""
    imgs = []
    VML = "urn:schemas-microsoft-com:vml"
    for blip in el.iter(_q(A, "blip")):
        rid = blip.get(_q(R, "embed"))
        if rid and rid in rels:
            fname = rels[rid].split("/")[-1]
            media_set.add(fname)
            imgs.append(
                f'<img class="docx-img" src="/api/v1/product-bible/__KEY__/media/{_esc(fname)}" alt="{_esc(fname)}" />'
            )
    for imgd in el.iter(_q(VML, "imagedata")):
        rid = imgd.get(_q(R, "id")) or imgd.get("r:id")
        if rid and rid in rels:
            fname = rels[rid].split("/")[-1]
            media_set.add(fname)
            imgs.append(
                f'<img class="docx-img" src="/api/v1/product-bible/__KEY__/media/{_esc(fname)}" alt="{_esc(fname)}" />'
            )
    return imgs


def _table_html(tbl: ET.Element, outline_map: dict, rels: dict, media_set: set) -> str:
    rows = []
    for tr in tbl.findall(_q(W, "tr")):
        cells = []
        for tc in tr.findall(_q(W, "tc")):
            cell_html = ""
            for child in tc:
                tag = _strip_ns(child.tag)
                if tag == "p":
                    cell_html += _paragraph_html(child, outline_map)
                    cell_html += "".join(_extract_images(child, rels, media_set))
                elif tag == "tbl":
                    cell_html += _table_html(child, outline_map, rels, media_set)
            cells.append(f"<td>{cell_html}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return '<table class="docx-table"><tbody>' + "".join(rows) + "</tbody></table>"


def _extract_blip_rel(pkg_rels: dict, embed_rid: str) -> str | None:
    return pkg_rels.get(embed_rid)


def docx_to_html(docx_path: str) -> dict:
    """解析 docx，返回 {html, title, updated_at, media: set(filename)}。"""
    z = zipfile.ZipFile(docx_path)
    names = set(z.namelist())

    # 样式映射
    outline_map = {}
    if "word/styles.xml" in names:
        styles_root = ET.fromstring(z.read("word/styles.xml"))
        outline_map = _style_outline_map(styles_root)

    # 文档关系（drawing blip -> media 目标）
    rels = {}
    if "word/_rels/document.xml.rels" in names:
        rel_root = ET.fromstring(z.read("word/_rels/document.xml.rels"))
        for rel in rel_root:
            rid = rel.get("Id")
            tgt = rel.get("Target")
            if tgt and not tgt.startswith("/"):
                tgt = "word/" + tgt.lstrip("./")
            rels[rid] = tgt

    media_set: set[str] = set()

    # 优先取文档核心属性标题
    title = ""
    if "docProps/core.xml" in names:
        try:
            core = ET.fromstring(z.read("docProps/core.xml"))
            for t in core.iter():
                if _strip_ns(t.tag) == "title" and (t.text or "").strip():
                    title = t.text.strip()
                    break
        except Exception:
            pass

    doc_root = ET.fromstring(z.read("word/document.xml"))
    body = doc_root.find(_q(W, "body"))
    if body is None:
        # 兜底：整个 document.xml
        body = doc_root

    out: list[str] = []
    seen_heading = False
    leading: list[str] = []

    for el in body:
        tag = _strip_ns(el.tag)
        if tag == "p":
            ph = _paragraph_html(el, outline_map)
            plain = "".join(t.text or "" for t in el.iter(_q(W, "t"))).strip()
            if ph:
                if ph.startswith("<h"):
                    seen_heading = True
                elif not seen_heading:
                    leading.append(plain)
                out.append(ph)
            # 段落内嵌图片（inline drawing / VML）
            out.extend(_extract_images(el, rels, media_set))
        elif tag == "tbl":
            out.append(_table_html(el, outline_map, rels, media_set))
        elif tag == "drawing":
            out.extend(_extract_images(el, rels, media_set))
        elif tag in ("sectPr",):
            continue
        else:
            out.extend(_extract_images(el, rels, media_set))

    # 无核心属性标题时，优先用封面文字（封面短标题），否则回退默认名
    if not title:
        cover = " ".join(x for x in leading if x).strip()
        if cover and len(cover) <= 40:
            title = cover
        else:
            title = "电子协议支撑服务能力白皮书"

    html = "\n".join(out)

    # 更新日期：尝试从文件 mtime 回退
    updated_at = ""
    try:
        mtime = os.path.getmtime(docx_path)
        import datetime
        updated_at = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
    except Exception:
        updated_at = ""

    return {
        "html": html,
        "title": title or "电子协议支撑服务能力白皮书",
        "updated_at": updated_at,
        "media": media_set,
    }


# ---------------------------------------------------------------------------
# EMF -> BMP 光栅化（ctypes / Windows GDI，零依赖）
# ---------------------------------------------------------------------------
def emf_to_bmp(emf_bytes: bytes) -> bytes | None:
    """把 EMF 字节光栅化为 BMP 文件字节；失败返回 None。仅 Windows 有效。"""
    if os.name != "nt":
        return None
    try:
        fd, tmp = tempfile.mkstemp(suffix=".emf")
        with os.fdopen(fd, "wb") as f:
            f.write(emf_bytes)
        return _emf_file_to_bmp(tmp)
    except Exception:
        return None
    finally:
        try:
            os.remove(tmp)
        except Exception:
            pass


def _emf_file_to_bmp(path: str) -> bytes | None:
    gdi32 = ctypes.windll.gdi32
    user32 = ctypes.windll.user32

    # 关键：64 位系统下 HANDLE 是 64 位，必须声明 restype/argtypes 为指针宽度，
    # 否则 ctypes 默认按 32 位 c_int 截断句柄 -> GetEnhMetaFile/CreateCompatibleBitmap 全部失败。
    P = ctypes.c_void_p
    gdi32.GetEnhMetaFileW.argtypes = [ctypes.c_wchar_p]
    gdi32.GetEnhMetaFileW.restype = P
    gdi32.GetEnhMetaFileHeader.argtypes = [P, ctypes.c_uint, P]
    gdi32.GetEnhMetaFileHeader.restype = ctypes.c_uint
    gdi32.DeleteEnhMetaFile.argtypes = [P]
    gdi32.DeleteEnhMetaFile.restype = ctypes.c_int
    gdi32.GetDeviceCaps.argtypes = [P, ctypes.c_int]
    gdi32.GetDeviceCaps.restype = ctypes.c_int
    gdi32.CreateCompatibleDC.argtypes = [P]
    gdi32.CreateCompatibleDC.restype = P
    gdi32.CreateCompatibleBitmap.argtypes = [P, ctypes.c_int, ctypes.c_int]
    gdi32.CreateCompatibleBitmap.restype = P
    gdi32.SelectObject.argtypes = [P, P]
    gdi32.SelectObject.restype = P
    gdi32.GetStockObject.argtypes = [ctypes.c_int]
    gdi32.GetStockObject.restype = P
    gdi32.PatBlt.argtypes = [P, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
    gdi32.PatBlt.restype = ctypes.c_int
    gdi32.SetMapMode.argtypes = [P, ctypes.c_int]
    gdi32.SetMapMode.restype = ctypes.c_int
    gdi32.SetWindowExtEx.argtypes = [P, ctypes.c_int, ctypes.c_int, P]
    gdi32.SetWindowExtEx.restype = ctypes.c_int
    gdi32.SetViewportExtEx.argtypes = [P, ctypes.c_int, ctypes.c_int, P]
    gdi32.SetViewportExtEx.restype = ctypes.c_int
    gdi32.PlayEnhMetaFile.argtypes = [P, P, ctypes.POINTER(ctypes.wintypes.RECT)]
    gdi32.PlayEnhMetaFile.restype = ctypes.c_int
    gdi32.GetDIBits.argtypes = [P, P, ctypes.c_uint, ctypes.c_uint, P, P, ctypes.c_uint]
    gdi32.GetDIBits.restype = ctypes.c_int
    gdi32.DeleteObject.argtypes = [P]
    gdi32.DeleteObject.restype = ctypes.c_int
    gdi32.DeleteDC.argtypes = [P]
    gdi32.DeleteDC.restype = ctypes.c_int
    user32.GetDC.argtypes = [P]
    user32.GetDC.restype = P
    user32.ReleaseDC.argtypes = [P, P]
    user32.ReleaseDC.restype = ctypes.c_int

    hemf = gdi32.GetEnhMetaFileW(path)
    if not hemf:
        return None
    try:
        hdr_size = gdi32.GetEnhMetaFileHeader(hemf, 0, None)
        if not hdr_size:
            return None
        buf = ctypes.create_string_buffer(hdr_size)
        if not gdi32.GetEnhMetaFileHeader(hemf, hdr_size, buf):
            return None
        # ENHMETAHEADER: iType(4) nSize(4) rclBounds(16) rclFrame(16)
        fl, ft, fr, fb = struct.unpack_from("<llll", buf, 24)
        if (fr - fl) <= 0 or (fb - ft) <= 0:
            return None

        hscreen = user32.GetDC(0)
        if not hscreen:
            return None
        try:
            dpi_x = gdi32.GetDeviceCaps(hscreen, 88)  # LOGPIXELSX
            dpi_y = gdi32.GetDeviceCaps(hscreen, 90)  # LOGPIXELSY
        finally:
            user32.ReleaseDC(0, hscreen)

        # 0.01mm -> mm -> pixel
        px_w = max(1, int(round((fr - fl) / 100.0 / 25.4 * dpi_x)))
        px_h = max(1, int(round((fb - ft) / 100.0 / 25.4 * dpi_y)))
        # 限制极端尺寸，避免内存爆炸
        max_dim = 4096
        if px_w > max_dim or px_h > max_dim:
            scale = max_dim / max(px_w, px_h)
            px_w = int(px_w * scale)
            px_h = int(px_h * scale)

        hscreen = ctypes.windll.user32.GetDC(0)
        hdc = gdi32.CreateCompatibleDC(0)
        if not hdc:
            ctypes.windll.user32.ReleaseDC(0, hscreen)
            return None
        hbmp = gdi32.CreateCompatibleBitmap(hscreen, px_w, px_h)
        ctypes.windll.user32.ReleaseDC(0, hscreen)
        if not hbmp:
            gdi32.DeleteDC(hdc)
            return None
        old = gdi32.SelectObject(hdc, hbmp)
        # 白底（选入白色画刷后 PATCOPY 填充）
        white_brush = gdi32.GetStockObject(0)  # WHITE_BRUSH
        prev_brush = gdi32.SelectObject(hdc, white_brush)
        gdi32.PatBlt(hdc, 0, 0, px_w, px_h, 0x00F000F0)  # PATCOPY
        if prev_brush:
            gdi32.SelectObject(hdc, prev_brush)
        # 设置各向异性映射：窗口=.01mm 框，视口=像素
        gdi32.SetMapMode(hdc, 8)  # MM_ANISOTROPIC
        gdi32.SetWindowExtEx(hdc, fr - fl, fb - ft, None)
        gdi32.SetViewportExtEx(hdc, px_w, px_h, None)
        rc = ctypes.wintypes.RECT(0, 0, fr - fl, fb - ft)
        gdi32.PlayEnhMetaFile(hdc, hemf, ctypes.byref(rc))

        # 取位图像素（32bpp）
        bpp = 32
        row_size = ((px_w * bpp + 31) // 32) * 4
        img_size = row_size * px_h
        bits = ctypes.create_string_buffer(img_size)
        bmi = _BITMAPINFO()
        bmi.bmiHeader.biSize = 40
        bmi.bmiHeader.biWidth = px_w
        bmi.bmiHeader.biHeight = px_h
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = bpp
        bmi.bmiHeader.biCompression = 0
        bmi.bmiHeader.biSizeImage = 0
        ret = gdi32.GetDIBits(hdc, hbmp, 0, px_h, bits, ctypes.byref(bmi), 0)
        gdi32.SelectObject(hdc, old)
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(hdc)
        if not ret:
            return None
        return _bits_to_bmp(bytes(bits), px_w, px_h, bpp, row_size)
    finally:
        gdi32.DeleteEnhMetaFile(hemf)


def _screen_dc():
    return ctypes.windll.user32.GetDC(0)


class _BITMAPINFO(ctypes.Structure):
    class _BMIH(ctypes.Structure):
        _fields_ = [
            ("biSize", ctypes.c_uint32),
            ("biWidth", ctypes.c_int32),
            ("biHeight", ctypes.c_int32),
            ("biPlanes", ctypes.c_uint16),
            ("biBitCount", ctypes.c_uint16),
            ("biCompression", ctypes.c_uint32),
            ("biSizeImage", ctypes.c_uint32),
            ("biXPelsPerMeter", ctypes.c_int32),
            ("biYPelsPerMeter", ctypes.c_int32),
            ("biClrUsed", ctypes.c_uint32),
            ("biClrImportant", ctypes.c_uint32),
        ]

    _fields_ = [("bmiHeader", _BMIH)]


def _bits_to_bmp(pixel_bytes: bytes, w: int, h: int, bpp: int, row_size: int) -> bytes:
    # BMP 文件头 + 信息头 + 像素（bottom-up BGR/A）
    bpp = 32
    row_size = ((w * bpp + 31) // 32) * 4
    img_size = row_size * h
    # 像素是 BGRA bottom-up（GetDIBits 默认），直接写入
    data = pixel_bytes[:img_size]
    # 信息头
    info = struct.pack(
        "<IiiHHIIiiII",
        40, w, h, 1, bpp, 0, img_size, 0, 0, 0, 0,
    )
    file_header = struct.pack("<cHHL", b"M", 0, 0, 14 + 40)
    # 上面 file_header 长度不对，重做：BM(2) + size(4) + reserved(4) + offset(4)
    file_size = 14 + 40 + img_size
    file_header = struct.pack("<2sIHHI", b"BM", file_size, 0, 0, 14 + 40)
    return file_header + info + data
