"""需求交付 service：附件文件夹管理、DDD 用户故事生成、需求分析说明书生成。

所有路径基于 Obsidian vault 派生（config.REQUIREMENT_ATTACHMENT_DIR /
REQUIREMENT_DOC_DIR），与知识库同源，便于 Obsidian 直接索引。
"""
from __future__ import annotations

import os
import re
import shutil
from typing import Any, Dict, List, Optional

from docx import Document
from docx.oxml import OxmlElement
from docx.text.paragraph import Paragraph

from db.models import SentEmail
from core.config import settings


# ---------------------------------------------------------------------------
# 路径与文件夹
# ---------------------------------------------------------------------------
def _safe_name(name: str) -> str:
    """把需求标题转成安全的文件夹名片段。"""
    if not name:
        return "untitled"
    s = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", name).strip()
    s = re.sub(r'\s+', "_", s)
    return s[:40]


def _requirement_base(req_id: str) -> str:
    """需求级根目录名：REQ-XXXX_标题。"""
    item = None
    # 延迟导入避免循环；这里只取值
    return req_id


def _resolve_paths(req_id: str, req_name: Optional[str] = None) -> Dict[str, str]:
    vault = settings.OBSIDIAN_VAULT_PATH
    att_base = os.path.join(vault, settings.REQUIREMENT_ATTACHMENT_DIR)
    doc_base = os.path.join(vault, settings.REQUIREMENT_DOC_DIR)
    sub = f"{req_id}_{_safe_name(req_name or req_id)}"
    att_folder = os.path.join(att_base, sub)
    doc_folder = os.path.join(doc_base, sub)
    return {
        "att_base": att_base,
        "doc_base": doc_base,
        "att_folder": att_folder,
        "doc_folder": doc_folder,
    }


def init_folder(db, req_id: str) -> Dict[str, Any]:
    """创建附件文件夹与说明书归档文件夹（幂等），返回路径与当前附件列表。"""
    item = db.query(SentEmail).filter(SentEmail.req_id == req_id).first()
    req_name = item.req_name if item else None
    paths = _resolve_paths(req_id, req_name)
    os.makedirs(paths["att_folder"], exist_ok=True)
    os.makedirs(paths["doc_folder"], exist_ok=True)
    attachments = _list_attachments_from(paths["att_folder"])
    return {
        "req_id": req_id,
        "attachment_folder": paths["att_folder"],
        "doc_folder": paths["doc_folder"],
        "attachments": attachments,
    }


def _human_size(num: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024:
            return f"{num:.0f} {unit}" if unit == "B" else f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} TB"


def _list_attachments_from(folder: str) -> List[Dict[str, Any]]:
    if not os.path.isdir(folder):
        return []
    out = []
    for fn in sorted(os.listdir(folder)):
        fp = os.path.join(folder, fn)
        if os.path.isfile(fp):
            sz = os.path.getsize(fp)
            out.append({"name": fn, "bytes": sz, "size": _human_size(sz)})
    return out


def list_attachments(db, req_id: str) -> List[Dict[str, Any]]:
    item = db.query(SentEmail).filter(SentEmail.req_id == req_id).first()
    paths = _resolve_paths(req_id, item.req_name if item else None)
    return _list_attachments_from(paths["att_folder"])


def upload_attachment(db, req_id: str, filename: str, content: bytes) -> Dict[str, Any]:
    item = db.query(SentEmail).filter(SentEmail.req_id == req_id).first()
    paths = _resolve_paths(req_id, item.req_name if item else None)
    os.makedirs(paths["att_folder"], exist_ok=True)
    safe_fn = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", filename)
    fp = os.path.join(paths["att_folder"], safe_fn)
    with open(fp, "wb") as f:
        f.write(content)
    return {"name": safe_fn, "bytes": len(content), "size": _human_size(len(content))}


def delete_attachment(db, req_id: str, filename: str) -> bool:
    item = db.query(SentEmail).filter(SentEmail.req_id == req_id).first()
    paths = _resolve_paths(req_id, item.req_name if item else None)
    fp = os.path.join(paths["att_folder"], os.path.basename(filename))
    # 防止路径穿越：必须落在附件文件夹内
    if not os.path.abspath(fp).startswith(os.path.abspath(paths["att_folder"])):
        return False
    if os.path.isfile(fp):
        os.remove(fp)
        return True
    return False


# ---------------------------------------------------------------------------
# DDD 用户故事生成
# ---------------------------------------------------------------------------
# 系统/标题关键词 -> DDD 子域映射（领域层体现）
_DDD_MAP = [
    ("专线", "政企专线领域", "国际版专线受理"),
    ("短信", "集团短信领域", "短信实名制"),
    ("宽带", "家宽/宽带领域", "流失预警与挽回"),
    ("网关", "网络接入领域", "被动销户治理"),
    ("CRM", "客户经营领域", "客户受理与工单"),
    ("BOSS", "计费账务领域", "计费与用户状态"),
    ("数据", "数据资产领域", "经分与模型"),
    ("运营", "生产运营领域", "运营监控与保障"),
]


def _derive_ddd(req_name: str, system_name: Optional[str]) -> Dict[str, str]:
    text = f"{req_name or ''} {system_name or ''}"
    for kw, domain, sub in _DDD_MAP:
        if kw in text:
            return {
                "domain": domain,
                "subdomain": sub,
                "aggregate": "需求-评估-交付",
                "entity": "需求、用户故事、开发工单",
            }
    return {
        "domain": "政企需求交付",
        "subdomain": "需求评估与履约",
        "aggregate": "需求-评估-交付",
        "entity": "需求、用户故事、开发工单",
    }


def _split_features(text: str) -> List[str]:
    """把澄清内容拆成若干功能点（每个功能点生成一条用户故事）。"""
    if not text or not text.strip():
        return []
    lines = [l.strip() for l in text.replace("\r", "\n").split("\n")]
    feats: List[str] = []
    for l in lines:
        # 去前导编号 1. 1、 (1) ①
        l = re.sub(r"^[（(]?\d+[.、)）]?\s*", "", l).strip()
        if len(l) < 4:
            continue
        # 长句按 。；； 再切，并去掉每段可能残留的前导编号（如 2. ② (3)）
        for part in re.split(r"[。；;]", l):
            part = re.sub(r"^[（(]?\d+[.、)）]?\s*", "", part).strip()
            if len(part) >= 6:
                feats.append(part)
    # 去重 + 限制最多 6 条
    seen = set()
    uniq = []
    for f in feats:
        if f not in seen:
            seen.add(f)
            uniq.append(f)
    return uniq[:6]


def generate_user_stories(db, req_id: str, content: str) -> Dict[str, Any]:
    """基于澄清内容 + DDD 理念生成固定 4 段模板用户故事。"""
    item = db.query(SentEmail).filter(SentEmail.req_id == req_id).first()
    req_name = item.req_name if item else req_id
    system_name = item.system_name if item else None
    proposer = item.proposer if item else ""
    ddd = _derive_ddd(req_name, system_name)

    # 内容优先用澄清内容，回退到原始描述
    source = (content or "").strip() or (item.description or "" if item else "")
    if not source.strip():
        source = (
            f"{req_name}：需建设对应能力，支撑政企业务运营，"
            "在相关系统中实现受理、配置、查询与监控等闭环功能。"
        )

    features = _split_features(source)
    if not features:
        features = [source]

    role = "业务负责人员"
    stories = []
    for i, feat in enumerate(features, start=1):
        function = feat
        purpose = "支撑政企业务数字化运营，保障业务连续性与客户体验"
        title = f"US{i}：作为{role}，希望{function}，以便{purpose}"
        desc = (
            f"【故事描述】{feat}。该需求来源于政企业务实际运营场景，"
            f"需在「{ddd['subdomain']}」相关系统中实现上述能力，"
            "以保障业务连续性与客户体验，并支持端到端的功能验证。"
        )
        scene = (
            f"【故事场景】当业务人员处理「{feat}」相关操作时，系统应提供对应的功能入口与数据支撑，"
            "使其能够在一次完整流程内完成目标操作，并获得明确的结果反馈；"
            "若操作失败，应给出可定位的提示。"
        )
        acceptance = [f"验证{function}功能是否成功实现"]
        stories.append({
            "seq": i,
            "title": title,
            "desc": desc,
            "scene": scene,
            "acceptance": acceptance,
            "ddd": ddd,
        })

    return {"req_id": req_id, "ddd": ddd, "proposer": proposer, "stories": stories}


# ---------------------------------------------------------------------------
# 需求分析说明书生成
# ---------------------------------------------------------------------------
def _find_heading_index(paras, text, style_contains: str) -> int:
    for i, p in enumerate(paras):
        if text in p.text and style_contains in p.style.name:
            return i
    return -1


def _insert_after(anchor: Paragraph, text: str, style_name: Optional[str] = None, doc=None) -> Paragraph:
    """在 anchor 段落之后插入一个新段落并返回其对象（用于链式插入）。

    style_name 存在时应用段落样式；doc 必须传入 Document 对象以便查 styles
    （anchor._parent 是 _Body，无 .styles 属性，不能直接用）。
    """
    new_p = OxmlElement("w:p")
    anchor._element.addnext(new_p)
    para = Paragraph(new_p, anchor._parent)
    if style_name and doc is not None:
        try:
            para.style = doc.styles[style_name]
        except KeyError:
            pass
    if text:
        para.add_run(text)
    return para


def generate_doc(db, req_id: str, stories: List[Dict[str, Any]], clarification: str = "") -> Dict[str, Any]:
    """基于固定模板生成《需求分析说明书》，仅填充第1/2/3章，其余复用模板。

    第1章 基本信息（表格）：需求单编号、需求提出人
    第2章 用户故事-背景以及业务总体描述：原始需求内容/澄清
    第3章 用户故事-用户Story：自动填充 US1/US2...（固定4段模板）
    第4章 需求检查项 / 第5章 版本历史：保持模板原样
    """
    item = db.query(SentEmail).filter(SentEmail.req_id == req_id).first()
    req_name = item.req_name if item else req_id
    proposer = item.proposer if item else ""
    paths = _resolve_paths(req_id, req_name)
    os.makedirs(paths["doc_folder"], exist_ok=True)

    template = settings.REQUIREMENT_DOC_TEMPLATE
    if not os.path.isfile(template):
        raise FileNotFoundError(f"模板不存在：{template}")
    doc = Document(template)
    paras = doc.paragraphs

    # ---- 第1章 基本信息（templates 首张表）----
    if doc.tables:
        tbl = doc.tables[0]
        if len(tbl.rows) >= 2:
            tbl.rows[1].cells[0].text = req_id              # 需求单编号
            tbl.rows[1].cells[2].text = proposer or ""       # 需求提出人

    # ---- 第2章 背景以及业务总体描述 ----
    idx_bg = _find_heading_index(paras, "背景以及业务总体描述", "Heading 3")
    if idx_bg >= 0 and idx_bg + 1 < len(paras):
        bg_body = paras[idx_bg + 1]
        bg_text = (clarification or "").strip() or (item.description or "" if item else "")
        if not bg_text:
            bg_text = req_name
        bg_body.text = f"【原始需求内容】{bg_text}"

    # ---- 第3章 用户Story：清除旧 US 区块，按生成结果填充 ----
    idx_story = _find_heading_index(paras, "用户Story", "Heading 3")
    idx_check = _find_heading_index(paras, "需求检查项", "Heading 2")
    if idx_story >= 0 and idx_check > idx_story:
        # 删除 idx_story+1 .. idx_check-1 之间的旧段落（原模板 US1/US2 及其正文）
        old = [paras[i] for i in range(idx_story + 1, idx_check)]
        for p in old:
            p._element.getparent().remove(p._element)
        # 链式插入新故事
        anchor = paras[idx_story]
        for st in stories:
            anchor = _insert_after(anchor, st["title"], "Heading 4", doc)
            anchor = _insert_after(anchor, f"Story功能描述\n{st['desc']}", None, doc)
            anchor = _insert_after(anchor, f"Story场景\n{st['scene']}", None, doc)
            anchor = _insert_after(anchor, "验收标准\n" + "；".join(st["acceptance"]), None, doc)

    # ---- 落盘 ----
    out_name = f"{req_name or req_id}需求分析说明书.docx"
    out_path = os.path.join(paths["doc_folder"], out_name)
    doc.save(out_path)

    rel = os.path.relpath(out_path, settings.OBSIDIAN_VAULT_PATH)
    url = "obsidian://open?path=" + out_path
    return {
        "req_id": req_id,
        "file": out_name,
        "path": out_path,
        "url": url,
        "relative_path": rel,
    }
