"""需求与交付模块增强 service：环节状态时间日志 / 开发事件 / 操作手册（按系统）。

环节模型（与前端 RequirementDeliveryView 6 步工作流一一对应）：
  collect(需求采集) → evaluate(团队评估) → story(用户故事) → doc(生成文档)
  → dev(启动开发) → deploy(生产部署)

时间采集原则：
  - 进入时间全自动：状态变更(dev/deploy)、首条评估、故事落库、生成文档、打开工作流(collect)
  - 完成时间 = 下一环节进入时间（自动补齐）
  - 存量需求首次访问时按现有数据推导回填（source=backfill），可手工修正（source=manual）
"""
from __future__ import annotations

import os
import re
from datetime import datetime, date
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from core.config import settings
from core.exceptions import NotFoundException, ValidationException
from db.models import (
    PmwbReqDevEvent,
    PmwbReqManual,
    PmwbRequirementEvaluation,
    PmwbRequirementExt,
    PmwbRequirementStageLog,
    PmwbUserStory,
    SentEmail,
)

# ---------------------------------------------------------------------------
# 环节定义
# ---------------------------------------------------------------------------
STAGE_ORDER = ["collect", "evaluate", "story", "doc", "dev", "deploy"]

STAGE_LABELS = {
    "collect": "需求采集",
    "evaluate": "团队评估",
    "story": "用户故事",
    "doc": "生成文档",
    "dev": "启动开发",
    "deploy": "生产部署",
}

# 操作手册可上传的跟踪状态（老大确认：已采纳/开发中/已上线均可）
MANUAL_ALLOWED_STATUS = ("accepted", "dev", "closed")

# 开发事件类型
DEV_EVENT_TYPES = {
    "dev_start": "开发启动",
    "joint_test": "联调提测",
    "test": "测试",
    "bugfix": "缺陷修复",
    "release_ready": "上线准备",
    "other": "其他",
}


def _fmt(v) -> Optional[str]:
    return v.strftime("%Y-%m-%d %H:%M") if isinstance(v, datetime) else None


# ---------------------------------------------------------------------------
# 环节时间日志：写入
# ---------------------------------------------------------------------------
def record_stage_entered(
    db: Session,
    req_id: str,
    stage: str,
    at: Optional[datetime] = None,
    source: str = "auto",
) -> Optional[PmwbRequirementStageLog]:
    """记录某环节进入时间（幂等：已有记录则不覆盖）；同时补齐更早环节的完成时间。"""
    if stage not in STAGE_ORDER:
        return None
    existing = (
        db.query(PmwbRequirementStageLog)
        .filter(PmwbRequirementStageLog.req_id == req_id, PmwbRequirementStageLog.stage == stage)
        .first()
    )
    if existing:
        return existing
    entered = at or datetime.now()
    log = PmwbRequirementStageLog(req_id=req_id, stage=stage, entered_at=entered, source=source)
    db.add(log)
    # 更早的环节若完成时间为空，用本环节进入时间补齐
    idx = STAGE_ORDER.index(stage)
    for prev in STAGE_ORDER[:idx]:
        prev_log = (
            db.query(PmwbRequirementStageLog)
            .filter(PmwbRequirementStageLog.req_id == req_id, PmwbRequirementStageLog.stage == prev)
            .first()
        )
        if prev_log and prev_log.left_at is None:
            prev_log.left_at = entered
    db.commit()
    db.refresh(log)
    return log


def _record_collect(db: Session, req_id: str) -> None:
    """collect 环节进入时间 = 需求最早一封邮件的创建时间（兜底当前时间）。"""
    earliest = (
        db.query(SentEmail.created_at)
        .filter(SentEmail.req_id == req_id)
        .order_by(SentEmail.id.asc())
        .first()
    )
    at = earliest[0] if earliest and earliest[0] else None
    record_stage_entered(db, req_id, "collect", at=at)


# ---------------------------------------------------------------------------
# 环节时间日志：读取（含存量回填）
# ---------------------------------------------------------------------------
def _backfill_stage(db: Session, req_id: str, stage: str, at: Optional[datetime]) -> None:
    if at is None:
        return
    record_stage_entered(db, req_id, stage, at=at, source="backfill")


def get_stage_logs(db: Session, req_id: str) -> Dict[str, Any]:
    """返回 6 个环节的时间日志；缺失的按现有数据推导回填（一次性）。"""
    item = db.query(SentEmail).filter(SentEmail.req_id == req_id).first()
    if not item:
        raise NotFoundException(f"需求不存在：{req_id}")
    ext = db.query(PmwbRequirementExt).filter(PmwbRequirementExt.req_id == req_id).first()

    logs = {
        log.stage: log
        for log in db.query(PmwbRequirementStageLog)
        .filter(PmwbRequirementStageLog.req_id == req_id)
        .all()
    }

    # ---- 存量回填（无记录时按现有数据推导） ----
    if "collect" not in logs:
        _record_collect(db, req_id)
        logs = {
            log.stage: log
            for log in db.query(PmwbRequirementStageLog)
            .filter(PmwbRequirementStageLog.req_id == req_id)
            .all()
        }
    if "evaluate" not in logs:
        first_eval = (
            db.query(PmwbRequirementEvaluation.created_at)
            .filter(PmwbRequirementEvaluation.req_id == req_id)
            .order_by(PmwbRequirementEvaluation.created_at.asc())
            .first()
        )
        if first_eval and first_eval[0]:
            _backfill_stage(db, req_id, "evaluate", first_eval[0])
    if "story" not in logs:
        first_story = (
            db.query(PmwbUserStory.created_at)
            .filter(PmwbUserStory.req_id == req_id)
            .order_by(PmwbUserStory.created_at.asc())
            .first()
        )
        if first_story and first_story[0]:
            _backfill_stage(db, req_id, "story", first_story[0])
    if "doc" not in logs:
        # 推导：需求文件夹内已生成的需求分析说明书文件 mtime
        at = _derive_doc_time(req_id, item.req_name)
        if at:
            _backfill_stage(db, req_id, "doc", at)
    status = (ext.status if ext else None) or "proposed"
    if "dev" not in logs and status in ("dev", "closed"):
        # 进入开发时间无法精确考证，用 ext 更新时间近似（标记 backfill，可手工修正）
        if ext and ext.updated_at:
            _backfill_stage(db, req_id, "dev", ext.updated_at)
    if "deploy" not in logs and status == "closed":
        # 生产部署进入时间优先用实际交付日期（用户手工填写的权威值）
        if ext and ext.delivered_date:
            d = ext.delivered_date
            at = datetime(d.year, d.month, d.day) if isinstance(d, date) else None
            _backfill_stage(db, req_id, "deploy", at)

    # 重新查询（回填可能新增了记录）
    logs = {
        log.stage: log
        for log in db.query(PmwbRequirementStageLog)
        .filter(PmwbRequirementStageLog.req_id == req_id)
        .all()
    }

    items = []
    for stage in STAGE_ORDER:
        log = logs.get(stage)
        items.append(
            {
                "stage": stage,
                "label": STAGE_LABELS[stage],
                "entered_at": _fmt(log.entered_at) if log else None,
                "left_at": _fmt(log.left_at) if log else None,
                "source": log.source if log else None,
            }
        )

    # 当前环节：最后一个有进入时间的环节
    current_stage = None
    for stage in STAGE_ORDER:
        if logs.get(stage):
            current_stage = stage
    return {"req_id": req_id, "current_stage": current_stage, "stages": items}


def _derive_doc_time(req_id: str, req_name: Optional[str]) -> Optional[datetime]:
    """按需求文件夹内的需求分析说明书文件推导「生成文档」环节时间。"""
    try:
        from services.requirement_delivery import _resolve_paths

        paths = _resolve_paths(req_id, req_name)
        folder = paths["folder"]
        if not os.path.isdir(folder):
            return None
        for fn in os.listdir(folder):
            fp = os.path.join(folder, fn)
            if os.path.isfile(fp) and "需求分析说明书" in fn:
                return datetime.fromtimestamp(os.path.getmtime(fp))
    except Exception:  # noqa: BLE001
        pass
    return None


def update_stage_log(
    db: Session, req_id: str, stage: str, entered_at: Optional[str], left_at: Optional[str]
) -> Dict[str, Any]:
    """手工修正环节时间。"""
    if stage not in STAGE_ORDER:
        raise ValidationException(f"非法环节：{stage}")

    def _parse(v: Optional[str]) -> Optional[datetime]:
        if not v:
            return None
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(v, fmt)
            except ValueError:
                continue
        raise ValidationException(f"时间格式不正确：{v}（支持 YYYY-MM-DD HH:MM）")

    log = (
        db.query(PmwbRequirementStageLog)
        .filter(PmwbRequirementStageLog.req_id == req_id, PmwbRequirementStageLog.stage == stage)
        .first()
    )
    if not log:
        log = PmwbRequirementStageLog(req_id=req_id, stage=stage, entered_at=_parse(entered_at), source="manual")
        db.add(log)
    else:
        log.entered_at = _parse(entered_at)
        log.left_at = _parse(left_at)
        log.source = "manual"
    db.commit()
    db.refresh(log)
    return {"stage": stage, "entered_at": _fmt(log.entered_at), "left_at": _fmt(log.left_at), "source": log.source}


def on_status_changed(db: Session, req_id: str, old_status: Optional[str], new_status: Optional[str]) -> None:
    """跟踪状态变更钩子：记录 dev/deploy 环节进入时间 + 自动插入「启动开发」事件。"""
    if old_status == new_status:
        return
    if new_status == "dev":
        record_stage_entered(db, req_id, "dev")
        _ensure_dev_start_event(db, req_id)
    elif new_status == "closed":
        record_stage_entered(db, req_id, "deploy")


# ---------------------------------------------------------------------------
# 开发事件
# ---------------------------------------------------------------------------
def _event_to_dict(ev: PmwbReqDevEvent) -> Dict[str, Any]:
    return {
        "id": ev.id,
        "req_id": ev.req_id,
        "event_time": _fmt(ev.event_time),
        "event_type": ev.event_type or "other",
        "event_type_label": DEV_EVENT_TYPES.get(ev.event_type or "other", "其他"),
        "title": ev.title or "",
        "content": ev.content or "",
        "created_at": _fmt(ev.created_at),
        "updated_at": _fmt(ev.updated_at),
    }


def _ensure_dev_start_event(db: Session, req_id: str) -> None:
    """状态切到「开发中」时自动补一条「启动开发」事件（已有则跳过）。"""
    exists = (
        db.query(PmwbReqDevEvent)
        .filter(PmwbReqDevEvent.req_id == req_id, PmwbReqDevEvent.event_type == "dev_start")
        .first()
    )
    if exists:
        return
    ev = PmwbReqDevEvent(
        req_id=req_id,
        event_time=datetime.now(),
        event_type="dev_start",
        title="启动开发",
        content="跟踪状态切换为「开发中」，自动记录。",
    )
    db.add(ev)
    db.commit()


def list_dev_events(db: Session, req_id: str) -> List[Dict[str, Any]]:
    evs = (
        db.query(PmwbReqDevEvent)
        .filter(PmwbReqDevEvent.req_id == req_id)
        .order_by(PmwbReqDevEvent.event_time.desc(), PmwbReqDevEvent.id.desc())
        .all()
    )
    return [_event_to_dict(ev) for ev in evs]


def _parse_dt(v: Optional[str], field: str) -> Optional[datetime]:
    if not v:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(v, fmt)
        except ValueError:
            continue
    raise ValidationException(f"{field} 格式不正确：{v}（支持 YYYY-MM-DD HH:MM）")


def create_dev_event(db: Session, req_id: str, obj_in: Dict[str, Any]) -> Dict[str, Any]:
    event_type = obj_in.get("event_type") or "other"
    if event_type not in DEV_EVENT_TYPES:
        raise ValidationException(f"非法事件类型：{event_type}")
    title = (obj_in.get("title") or "").strip()
    if not title:
        raise ValidationException("事件标题不能为空")
    ev = PmwbReqDevEvent(
        req_id=req_id,
        event_time=_parse_dt(obj_in.get("event_time"), "事件时间") or datetime.now(),
        event_type=event_type,
        title=title,
        content=obj_in.get("content") or "",
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return _event_to_dict(ev)


def update_dev_event(db: Session, req_id: str, event_id: int, obj_in: Dict[str, Any]) -> Dict[str, Any]:
    ev = db.query(PmwbReqDevEvent).filter(PmwbReqDevEvent.id == event_id, PmwbReqDevEvent.req_id == req_id).first()
    if not ev:
        raise NotFoundException(f"开发事件不存在：{event_id}")
    event_type = obj_in.get("event_type") or ev.event_type
    if event_type not in DEV_EVENT_TYPES:
        raise ValidationException(f"非法事件类型：{event_type}")
    title = (obj_in.get("title") or "").strip()
    if not title:
        raise ValidationException("事件标题不能为空")
    ev.event_type = event_type
    ev.title = title
    ev.content = obj_in.get("content") or ""
    if obj_in.get("event_time"):
        ev.event_time = _parse_dt(obj_in.get("event_time"), "事件时间")
    db.commit()
    db.refresh(ev)
    return _event_to_dict(ev)


def delete_dev_event(db: Session, req_id: str, event_id: int) -> bool:
    ev = db.query(PmwbReqDevEvent).filter(PmwbReqDevEvent.id == event_id, PmwbReqDevEvent.req_id == req_id).first()
    if not ev:
        return False
    db.delete(ev)
    db.commit()
    return True


# ---------------------------------------------------------------------------
# 操作手册（按系统）
# ---------------------------------------------------------------------------
def _manual_to_dict(m: PmwbReqManual) -> Dict[str, Any]:
    ext = os.path.splitext(m.file_name or "")[1].lower()
    previewable = ext in (".pdf", ".doc", ".docx")
    size = 0
    try:
        ap = manual_abs_path(m)
        if ap and os.path.exists(ap):
            size = os.path.getsize(ap)
    except Exception:
        pass
    return {
        "id": m.id,
        "req_id": m.req_id,
        "system_name": m.system_name,
        "file_name": m.file_name,
        "local_path": m.local_path,
        "obsidian_path": m.obsidian_path,
        "note": m.note,
        "uploaded_by": m.uploaded_by,
        "size": size,
        "archived_at": _fmt(m.archived_at),
        "previewable": previewable,
        "created_at": _fmt(m.created_at),
        "updated_at": _fmt(m.updated_at),
    }


def list_manual_systems(db: Session, req_id: str) -> Dict[str, Any]:
    """按「当前需求的团队（评估记录系统）」列手册；没有手册的系统也展示（暂无操作手册）。"""
    evals = (
        db.query(PmwbRequirementEvaluation)
        .filter(PmwbRequirementEvaluation.req_id == req_id)
        .all()
    )
    # 系统 → SA 映射（保留首个非空）
    sa_map: Dict[str, str] = {}
    for ev in evals:
        sys_name = (ev.system_name or "").strip()
        if sys_name and sys_name not in sa_map:
            sa_map[sys_name] = (ev.sa_name or "").strip()
    manuals = {
        m.system_name: m
        for m in db.query(PmwbReqManual).filter(PmwbReqManual.req_id == req_id).all()
    }
    # 手册表里有、但评估记录已删除的系统也要展示
    for sys_name in manuals:
        if sys_name not in sa_map:
            sa_map[sys_name] = ""
    systems = []
    for sys_name, sa_name in sa_map.items():
        m = manuals.get(sys_name)
        systems.append(
            {
                "system_name": sys_name,
                "sa_name": sa_name,
                "manual": _manual_to_dict(m) if m else None,
            }
        )
    # 有手册的排前面
    systems.sort(key=lambda s: (s["manual"] is None, s["system_name"]))
    return {"req_id": req_id, "systems": systems}


def upload_manual(
    db: Session,
    req_id: str,
    system_name: str,
    filename: str,
    content: bytes,
    note: str = "",
    uploaded_by: str = "",
) -> Dict[str, Any]:
    """上传/替换某系统的操作手册（一系统一份）。

    状态约束：accepted/dev/closed 均可（老大确认）。
    文件落盘：需求分析说明书文件夹/操作手册/{系统名}_{原文件名}。
    兼容：同步登记 ext.deliverables（note=操作手册-{系统}），归档到业务知识流程复用。
    """
    ext = db.query(PmwbRequirementExt).filter(PmwbRequirementExt.req_id == req_id).first()
    if not ext:
        raise NotFoundException(f"需求不存在：{req_id}")
    if (ext.status or "proposed") not in MANUAL_ALLOWED_STATUS:
        raise ValidationException("操作手册在需求「已采纳/开发中/已上线」阶段可上传")
    system_name = (system_name or "").strip()
    if not system_name:
        raise ValidationException("请选择/填写所属系统（按团队上传，区分系统）")

    from services.requirement_delivery import _resolve_paths

    item = db.query(SentEmail).filter(SentEmail.req_id == req_id).first()
    paths = _resolve_paths(req_id, item.req_name if item else None)
    manual_dir = os.path.join(paths["folder"], "操作手册")
    os.makedirs(manual_dir, exist_ok=True)
    safe_sys = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", system_name).strip() or "系统"
    safe_fn = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", filename or "操作手册")
    stored_name = f"{safe_sys}_{safe_fn}"
    fp = os.path.join(manual_dir, stored_name)
    with open(fp, "wb") as f:
        f.write(content)
    rel_local = os.path.relpath(fp, settings.OBSIDIAN_VAULT_PATH).replace("\\", "/")

    existing = (
        db.query(PmwbReqManual)
        .filter(PmwbReqManual.req_id == req_id, PmwbReqManual.system_name == system_name)
        .first()
    )
    replaced = False
    if existing:
        # 替换：删除旧文件（若路径不同），重置归档状态
        if existing.local_path and existing.local_path != rel_local:
            old_fp = os.path.join(settings.OBSIDIAN_VAULT_PATH, existing.local_path)
            if os.path.isfile(old_fp):
                try:
                    os.remove(old_fp)
                except OSError:
                    pass
        existing.file_name = filename
        existing.local_path = rel_local
        existing.note = note
        existing.uploaded_by = uploaded_by
        existing.obsidian_path = None
        existing.archived_at = None
        m = existing
        replaced = True
    else:
        m = PmwbReqManual(
            req_id=req_id,
            system_name=system_name,
            file_name=filename,
            local_path=rel_local,
            note=note,
            uploaded_by=uploaded_by,
        )
        db.add(m)
    db.commit()
    db.refresh(m)

    # 兼容登记 deliverables（归档到业务知识入口复用）；替换时移除旧条目
    try:
        from services.obsidian_link import add_requirement_deliverable, get_requirement_deliverables, remove_requirement_deliverable

        items = get_requirement_deliverables(db, req_id)
        tag = f"操作手册-{system_name}"
        for i in range(len(items) - 1, -1, -1):
            if items[i].get("note") == tag:
                remove_requirement_deliverable(db, req_id, i)
        add_requirement_deliverable(db, req_id, filename, rel_local, note=tag)
    except Exception:  # noqa: BLE001 交付物登记失败不影响手册主流程
        pass

    data = _manual_to_dict(m)
    data["replaced"] = replaced
    return data


def get_manual(db: Session, req_id: str, manual_id: int) -> PmwbReqManual:
    m = db.query(PmwbReqManual).filter(PmwbReqManual.id == manual_id, PmwbReqManual.req_id == req_id).first()
    if not m:
        raise NotFoundException(f"操作手册不存在：{manual_id}")
    return m


def manual_abs_path(m: PmwbReqManual) -> str:
    if not m.local_path:
        raise NotFoundException("手册文件路径缺失")
    fp = os.path.join(settings.OBSIDIAN_VAULT_PATH, m.local_path)
    if not os.path.isfile(fp):
        raise NotFoundException("手册文件已不存在（可能被移动或删除）")
    return fp


def delete_manual(db: Session, req_id: str, manual_id: int) -> bool:
    m = db.query(PmwbReqManual).filter(PmwbReqManual.id == manual_id, PmwbReqManual.req_id == req_id).first()
    if not m:
        return False
    fp = os.path.join(settings.OBSIDIAN_VAULT_PATH, m.local_path) if m.local_path else None
    db.delete(m)
    db.commit()
    if fp and os.path.isfile(fp):
        try:
            os.remove(fp)
        except OSError:
            pass
    # 同步移除 deliverables 兼容条目
    try:
        from services.obsidian_link import get_requirement_deliverables, remove_requirement_deliverable

        items = get_requirement_deliverables(db, req_id)
        tag = f"操作手册-{m.system_name}"
        for i in range(len(items) - 1, -1, -1):
            if items[i].get("note") == tag:
                remove_requirement_deliverable(db, req_id, i)
    except Exception:  # noqa: BLE001
        pass
    return True


def manual_preview_html(m: PmwbReqManual) -> str:
    """docx 在线预览：mammoth 转 HTML；返回带基础样式的完整 HTML。"""
    fp = manual_abs_path(m)
    ext = os.path.splitext(fp)[1].lower()
    if ext != ".docx":
        raise ValidationException("仅 DOCX 支持在线预览，PDF 请直接打开，其他格式请下载查看")
    import mammoth

    with open(fp, "rb") as f:
        result = mammoth.convert_to_html(f)
    body = result.value or "<p>（文档内容为空）</p>"
    title = f"{m.system_name} · {m.file_name}"
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  body {{ font-family: "Microsoft YaHei", "PingFang SC", sans-serif; max-width: 900px;
         margin: 24px auto; padding: 0 20px 48px; color: #262626; line-height: 1.75; }}
  .doc-header {{ border-bottom: 1px solid #e0e0e0; padding-bottom: 12px; margin-bottom: 24px; }}
  .doc-header h1 {{ font-size: 18px; margin: 0 0 6px; }}
  .doc-header .meta {{ color: #888; font-size: 12.5px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
  td, th {{ border: 1px solid #d9d9d9; padding: 6px 10px; font-size: 13px; }}
  img {{ max-width: 100%; }}
</style>
</head>
<body>
<div class="doc-header">
  <h1>{m.file_name}</h1>
  <div class="meta">所属系统：{m.system_name} · 在线预览（由 DOCX 转换，排版与原文档略有差异）</div>
</div>
{body}
</body>
</html>"""
