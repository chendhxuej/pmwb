"""业务资料库 - 存量/增量汇聚服务。

设计原则：
1. **只登记指针，不搬迁物理文件**——原模块的下载/删除逻辑全部不受影响。
2. **幂等**——按 (source_type, source_id, rel_path_hash) 唯一约束去重，重复跑不产生脏数据。
3. **单源失败不阻断**——任一来源扫不动只记 error，其余来源照常入库。
4. **不覆盖人工成果**——已存在的条目只刷新体积/标题等事实字段，
   不动 category_id / note / tags 这些用户可能手工改过的值。

当前汇聚 6 个来源：运营工单、一线调研工单、需求交付物、开发交付物、重点工作交付物、需求操作手册。
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db.models import (
    PmwbDevDeliverable,
    PmwbDevTicket,
    PmwbKeyWork,
    PmwbKeyWorkDeliverable,
    PmwbMaterial,
    PmwbOperationIssue,
    PmwbReqInterfaceDoc,
    PmwbReqManual,
    PmwbRequirementExt,
    PmwbResearchIssue,
    SentEmail,
)
from utils import file_storage as fs

SOURCE_LABELS = {
    "operation_issue": "运营工单",
    "research_issue": "一线调研工单",
    "requirement": "需求交付物",
    "dev_deliverable": "开发交付物",
    "keywork_deliverable": "重点工作交付物",
    "req_manual": "需求操作手册",
    "interface_doc": "接口规范文档",
    "manual_upload": "手工上传",
}


def _to_pointer(raw: Optional[str], prefer_root: str = "vault") -> Optional[tuple[str, str]]:
    """把各种历史写法（绝对路径 / vault 相对路径）规约成 (storage_root, rel_path)。

    绝对路径只接受落在 vault 或 uploads 两个根之内的；其余返回 None（跳过并记 warn）。
    """
    if not raw:
        return None
    p = str(raw).replace("/", os.sep)
    vault = os.path.abspath(fs.vault_root())
    uploads = os.path.abspath(fs.uploads_root())

    if os.path.isabs(p):
        ap = os.path.abspath(p)
        if ap.startswith(vault + os.sep):
            return ("vault", os.path.relpath(ap, vault).replace(os.sep, "/"))
        if ap.startswith(uploads + os.sep):
            return ("uploads", os.path.relpath(ap, uploads).replace(os.sep, "/"))
        return None
    return (prefer_root, p.replace(os.sep, "/"))


def _upsert(
    db: Session,
    *,
    source_type: str,
    source_id: str,
    source_no: str = "",
    source_title: str = "",
    storage_root: str,
    rel_path: str,
    file_name: str,
    file_size: Optional[int] = None,
    domain_code: Optional[str] = None,
    uploaded_by: Optional[str] = None,
) -> str:
    """登记一条索引。返回 'added' | 'updated' | 'skipped'。"""
    rel_path = rel_path.replace("\\", "/")
    h = fs.path_hash(rel_path)
    existing = (
        db.query(PmwbMaterial)
        .filter(
            PmwbMaterial.source_type == source_type,
            PmwbMaterial.source_id == source_id,
            PmwbMaterial.rel_path_hash == h,
        )
        .first()
    )
    if existing:
        changed = False
        # 只刷新事实字段，不动 category_id / note / tags（用户可能手工改过）
        if file_size is not None and existing.file_size != file_size:
            existing.file_size = file_size
            changed = True
        if source_title and existing.source_title != source_title:
            existing.source_title = source_title
            changed = True
        if source_no and existing.source_no != source_no:
            existing.source_no = source_no
            changed = True
        return "updated" if changed else "skipped"

    ext = fs.file_ext(file_name)
    obj = PmwbMaterial(
        source_type=source_type,
        source_id=str(source_id),
        source_no=source_no or "",
        source_title=source_title or "",
        file_name=file_name,
        stored_name=os.path.basename(rel_path),
        storage_root=storage_root,
        rel_path=rel_path,
        rel_path_hash=h,
        file_size=file_size,
        file_ext=ext,
        file_type=fs.guess_mime(file_name),
        origin="auto",
        uploaded_by=uploaded_by,
        domain_code=domain_code,
    )
    db.add(obj)
    try:
        db.flush()
    except IntegrityError:
        # 兜底：理论上同 source 内已按名去重，此处仍防御并发/残留脏数据
        db.rollback()
        db.expunge(obj)
        existing = (
            db.query(PmwbMaterial)
            .filter(
                PmwbMaterial.source_type == source_type,
                PmwbMaterial.source_id == str(source_id),
                PmwbMaterial.rel_path_hash == h,
            )
            .first()
        )
        if existing:
            return "updated" if existing.file_size != file_size else "skipped"
        return "skipped"
    return "added"


def _parse_json_list(raw: Optional[str]) -> list:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []


# --------------------------------------------------------------- 各来源扫描
def _sync_operation(db: Session) -> dict:
    """运营工单附件：uploads/operation/{issue_id}/{name}"""
    stat = {"scanned": 0, "added": 0, "updated": 0, "skipped": 0, "warn": []}
    rows = db.query(PmwbOperationIssue).filter(
        PmwbOperationIssue.attachments.isnot(None),
        PmwbOperationIssue.attachments != "",
        PmwbOperationIssue.attachments != "[]",
    ).all()
    for issue in rows:
        seen_names: set[str] = set()
        for meta in _parse_json_list(issue.attachments):
            name = (meta or {}).get("name") if isinstance(meta, dict) else str(meta)
            if not name:
                continue
            if name in seen_names:  # 同一工单内同名附件去重（工单#50 历史脏数据）
                stat["warn"].append(f"工单#{issue.id} 跳过重复附件名：{name}")
                continue
            seen_names.add(name)
            stat["scanned"] += 1
            rel = f"operation/{issue.id}/{name}"
            full = os.path.join(fs.uploads_root(), "operation", str(issue.id), name)
            if not os.path.isfile(full):
                stat["warn"].append(f"工单#{issue.id} 附件缺失：{name}")
                continue
            size = (meta or {}).get("bytes") if isinstance(meta, dict) else None
            if not isinstance(size, int):
                size = os.path.getsize(full)
            r = _upsert(
                db,
                source_type="operation_issue",
                source_id=str(issue.id),
                source_no=issue.issue_no or "",
                source_title=issue.title or "",
                storage_root="uploads",
                rel_path=rel,
                file_name=name,
                file_size=size,
            )
            stat[r] += 1
    return stat


def _sync_research(db: Session) -> dict:
    """一线调研工单附件：uploads/research/{issue_id}/{name}"""
    stat = {"scanned": 0, "added": 0, "updated": 0, "skipped": 0, "warn": []}
    rows = db.query(PmwbResearchIssue).filter(
        PmwbResearchIssue.attachments.isnot(None),
        PmwbResearchIssue.attachments != "",
        PmwbResearchIssue.attachments != "[]",
    ).all()
    for issue in rows:
        seen_names: set[str] = set()
        for meta in _parse_json_list(issue.attachments):
            name = (meta or {}).get("name") if isinstance(meta, dict) else str(meta)
            if not name:
                continue
            if name in seen_names:  # 同一工单内同名附件去重（工单#50 历史脏数据）
                stat["warn"].append(f"工单#{issue.id} 跳过重复附件名：{name}")
                continue
            seen_names.add(name)
            stat["scanned"] += 1
            rel = f"research/{issue.id}/{name}"
            full = os.path.join(fs.uploads_root(), "research", str(issue.id), name)
            if not os.path.isfile(full):
                stat["warn"].append(f"调研工单#{issue.id} 附件缺失：{name}")
                continue
            r = _upsert(
                db,
                source_type="research_issue",
                source_id=str(issue.id),
                source_no=getattr(issue, "issue_no", "") or "",
                source_title=getattr(issue, "title", "") or "",
                storage_root="uploads",
                rel_path=rel,
                file_name=name,
                file_size=os.path.getsize(full),
            )
            stat[r] += 1
    return stat


def _sync_requirement(db: Session) -> dict:
    """需求直挂交付物：deliverables JSON，路径为 vault 相对路径。"""
    stat = {"scanned": 0, "added": 0, "updated": 0, "skipped": 0, "warn": []}
    rows = db.query(PmwbRequirementExt).filter(
        PmwbRequirementExt.deliverables.isnot(None),
        PmwbRequirementExt.deliverables != "",
        PmwbRequirementExt.deliverables != "[]",
    ).all()
    for ext in rows:
        email = db.query(SentEmail).filter(SentEmail.req_id == ext.req_id).first()
        title = (email.req_name if email else "") or ""
        for item in _parse_json_list(ext.deliverables):
            if not isinstance(item, dict):
                continue
            stat["scanned"] += 1
            raw = item.get("obsidian_path") or item.get("local_path")
            pointer = _to_pointer(raw, prefer_root="vault")
            if not pointer:
                stat["warn"].append(f"需求 {ext.req_id} 交付物路径无法解析：{raw}")
                continue
            root, rel = pointer
            full = fs.abs_path(root, rel)
            if not os.path.isfile(full):
                stat["warn"].append(f"需求 {ext.req_id} 交付物缺失：{rel}")
                continue
            r = _upsert(
                db,
                source_type="requirement",
                source_id=str(ext.req_id),
                source_no=ext.req_id,
                source_title=title,
                storage_root=root,
                rel_path=rel,
                file_name=item.get("file_name") or os.path.basename(rel),
                file_size=os.path.getsize(full),
                domain_code=ext.domain_code,
            )
            stat[r] += 1
    return stat


def _sync_dev_deliverable(db: Session) -> dict:
    stat = {"scanned": 0, "added": 0, "updated": 0, "skipped": 0, "warn": []}
    rows = db.query(PmwbDevDeliverable).all()
    for d in rows:
        stat["scanned"] += 1
        pointer = _to_pointer(d.obsidian_path or d.local_path, prefer_root="vault")
        if not pointer:
            stat["warn"].append(f"开发交付物#{d.id} 路径无法解析")
            continue
        root, rel = pointer
        full = fs.abs_path(root, rel)
        if not os.path.isfile(full):
            stat["warn"].append(f"开发交付物#{d.id} 文件缺失：{rel}")
            continue
        ticket = db.query(PmwbDevTicket).filter(PmwbDevTicket.id == d.ticket_id).first()
        r = _upsert(
            db,
            source_type="dev_deliverable",
            source_id=str(d.id),
            source_no=(ticket.ticket_no if ticket else "") or "",
            source_title=(ticket.title if ticket else "") or "",
            storage_root=root,
            rel_path=rel,
            file_name=d.original_name or d.file_name or os.path.basename(rel),
            file_size=d.file_size or os.path.getsize(full),
            uploaded_by=None,
        )
        stat[r] += 1
    return stat


def _sync_keywork_deliverable(db: Session) -> dict:
    stat = {"scanned": 0, "added": 0, "updated": 0, "skipped": 0, "warn": []}
    rows = db.query(PmwbKeyWorkDeliverable).all()
    for d in rows:
        stat["scanned"] += 1
        pointer = _to_pointer(d.obsidian_path or d.local_path, prefer_root="vault")
        if not pointer:
            stat["warn"].append(f"重点工作交付物#{d.id} 路径无法解析")
            continue
        root, rel = pointer
        full = fs.abs_path(root, rel)
        if not os.path.isfile(full):
            stat["warn"].append(f"重点工作交付物#{d.id} 文件缺失：{rel}")
            continue
        kw = db.query(PmwbKeyWork).filter(PmwbKeyWork.id == d.key_work_id).first()
        r = _upsert(
            db,
            source_type="keywork_deliverable",
            source_id=str(d.id),
            source_no="",
            source_title=(kw.title if kw else "") or "",
            storage_root=root,
            rel_path=rel,
            file_name=d.original_name or d.file_name or os.path.basename(rel),
            file_size=d.file_size or os.path.getsize(full),
            uploaded_by=d.uploaded_by,
        )
        stat[r] += 1
    return stat


def _sync_req_manual(db: Session) -> dict:
    stat = {"scanned": 0, "added": 0, "updated": 0, "skipped": 0, "warn": []}
    for m in db.query(PmwbReqManual).all():
        stat["scanned"] += 1
        pointer = _to_pointer(m.obsidian_path or m.local_path, prefer_root="vault")
        if not pointer:
            stat["warn"].append(f"操作手册#{m.id} 路径无法解析")
            continue
        root, rel = pointer
        full = fs.abs_path(root, rel)
        if not os.path.isfile(full):
            stat["warn"].append(f"操作手册#{m.id} 文件缺失：{rel}")
            continue
        r = _upsert(
            db,
            source_type="req_manual",
            source_id=str(m.id),
            source_no=m.req_id or "",
            source_title=f"{m.req_id} {m.system_name}".strip(),
            storage_root=root,
            rel_path=rel,
            file_name=m.file_name or os.path.basename(rel),
            file_size=os.path.getsize(full),
            uploaded_by=m.uploaded_by,
        )
        stat[r] += 1
    return stat




def _sync_interface_doc(db: Session) -> dict:
    """接口规范文档：PmwbReqInterfaceDoc，归档路径为 obsidian_path（vault 相对路径）。"""
    stat = {"scanned": 0, "added": 0, "updated": 0, "skipped": 0, "warn": []}
    for d in db.query(PmwbReqInterfaceDoc).all():
        stat["scanned"] += 1
        # 优先用归档后的 obsidian_path，回退到 local_path
        pointer = _to_pointer(d.obsidian_path or d.local_path, prefer_root="vault")
        if not pointer:
            stat["warn"].append(f"接口规范#{d.id} 路径无法解析")
            continue
        root, rel = pointer
        full = fs.abs_path(root, rel)
        if not os.path.isfile(full):
            stat["warn"].append(f"接口规范#{d.id} 文件缺失：{rel}")
            continue
        r = _upsert(
            db,
            source_type="interface_doc",
            source_id=str(d.id),
            source_no=d.req_id or "",
            source_title=d.system_name or d.req_id or "",
            storage_root=root,
            rel_path=rel,
            file_name=d.file_name or os.path.basename(rel),
            file_size=os.path.getsize(full),
            uploaded_by=d.uploaded_by,
        )
        stat[r] += 1
    return stat

_SCANNERS = [
    ("operation_issue", _sync_operation),
    ("research_issue", _sync_research),
    ("requirement", _sync_requirement),
    ("dev_deliverable", _sync_dev_deliverable),
    ("keywork_deliverable", _sync_keywork_deliverable),
    ("req_manual", _sync_req_manual),
    ("interface_doc", _sync_interface_doc),
]


def sync_all(db: Session) -> dict:
    """全量扫描汇聚。单来源异常不阻断整体。"""
    sources: list[dict] = []
    total_added = 0

    for source_type, fn in _SCANNERS:
        try:
            stat = fn(db)
            db.commit()
            total_added += stat["added"]
            sources.append(
                {
                    "source_type": source_type,
                    "label": SOURCE_LABELS.get(source_type, source_type),
                    **stat,
                    "error": None,
                }
            )
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            sources.append(
                {
                    "source_type": source_type,
                    "label": SOURCE_LABELS.get(source_type, source_type),
                    "scanned": 0,
                    "added": 0,
                    "updated": 0,
                    "skipped": 0,
                    "warn": [],
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    return {
        "added": total_added,
        "sources": sources,
        "total": db.query(PmwbMaterial).count(),
    }


def find_orphans(db: Session) -> list[dict]:
    """找出索引存在但物理文件已丢失的条目（供页面提示或清理）。"""
    orphans = []
    for m in db.query(PmwbMaterial).filter(PmwbMaterial.origin == "auto").all():
        try:
            full = fs.abs_path(m.storage_root, m.rel_path)
        except Exception:
            orphans.append({"id": m.id, "file_name": m.file_name, "reason": "路径非法"})
            continue
        if not os.path.isfile(full):
            orphans.append({"id": m.id, "file_name": m.file_name, "reason": "原文件已删除"})
    return orphans
