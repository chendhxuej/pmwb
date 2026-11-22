"""PRD 知识同步（页面触发 → 计划任务 → 状态轮询）。

后端运行于 LocalSystem，读不到 chend 用户的 GCM 凭据，故不直接执行 git：
- trigger(): 写请求 JSON + 触发以用户身份注册的计划任务 PMWB-PRD-KnowledgeSync
- status():  读 worker 写回的状态 JSON
- available_systems(): 列可同步系统 + 仓库内业务子目录（供页面勾选）

唯一状态目录：settings.PRD_KNOWLEDGE_ROOT（D:\\项目\\knowledge）。
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from core.config import settings

TASK_NAME = "PMWB-PRD-KnowledgeSync"
SYSTEMS = [
    {"id": "CRM", "name": "CRM"},
    {"id": "BOSS", "name": "BOSS"},
    {"id": "ORDER_CENTER", "name": "订单中心"},
]
REQUEST_FILE = ".sync_request.json"
STATE_FILE = ".sync_state.json"
STALE_SECONDS = 1500  # 25min，与计划任务 ExecutionTimeLimit 一致


def _root() -> Path:
    return Path(settings.PRD_KNOWLEDGE_ROOT)


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:  # noqa: BLE001
        return {}


def _is_stale(ts: str | None) -> bool:
    if not ts:
        return True
    try:
        t = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return True
    return (datetime.now() - t).total_seconds() > STALE_SECONDS


def status() -> Dict[str, Any]:
    """当前同步状态。running 且超时 → 标记 stale，避免永久锁死页面。"""
    state = _read_json(_root() / STATE_FILE)
    st = state.get("status") or "idle"
    if st == "running" and _is_stale(state.get("started_at")):
        st = "stale"
    return {
        "status": st,
        "systems": state.get("systems") or [],
        "summary": state.get("summary"),
        "systems_detail": state.get("systems_detail") or [],
        "started_at": state.get("started_at"),
        "finished_at": state.get("finished_at"),
        "synced_at": state.get("synced_at"),
        "error": state.get("error"),
        "task_installed": _task_installed(),
    }


def _task_installed() -> bool:
    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command",
             f"(Get-ScheduledTask -TaskName '{TASK_NAME}' -ErrorAction SilentlyContinue).State"],
            capture_output=True, text=True, timeout=15,
        )
        return bool(proc.stdout and proc.stdout.strip() and "Ready" in proc.stdout)
    except Exception:  # noqa: BLE001
        return False


def available_systems() -> Dict[str, Any]:
    """可同步系统 + 每个系统仓库内的业务子目录（供页面手工勾选）。"""
    root = _root()
    result = []
    for s in SYSTEMS:
        sys_dir = root / s["id"]
        dirs: List[str] = []
        if sys_dir.is_dir():
            dirs = sorted(
                d.name for d in sys_dir.iterdir()
                if d.is_dir() and not d.name.startswith(".") and d.name != ".git"
            )
        result.append({
            "id": s["id"], "name": s["name"],
            "cloned": sys_dir.is_dir(),
            "dirs": dirs,
        })
    # 涉及系统（页面可勾选分析）来自需求工单实际数据；知识同步仍仅限有内网 Git 仓库的系统。
    try:
        from services.requirement import requirement_service
        from db.base import SessionLocal

        db = SessionLocal()
        try:
            involved = requirement_service.get_systems(db) or []
        finally:
            db.close()
    except Exception:  # noqa: BLE001 取数失败只列知识系统
        involved = []
    # 归一化：显示名按别名映射到 clone 目录 ID 再去重（订单中心 == ORDER_CENTER）
    alias = {"订单中心": "ORDER_CENTER", "ORDER_CENTER": "ORDER_CENTER"}
    known = {alias.get(x["id"], x["id"]) for x in result}
    involved_out, seen = [], set(known)
    for s in involved:
        norm = alias.get(s, s)
        if norm not in seen:
            seen.add(norm)
            involved_out.append(s)
    involved = involved_out
    return {
        "systems": result,
        "involved_systems": involved,
        "note": (
            "仅 CRM / BOSS / 订单中心 3 个系统已接入内网 Git 仓库可同步知识；"
            "需求工单涉及的其他系统可正常参与分析，但未建知识仓库，按无知识降级处理。"
        ),
    }


def trigger(systems: List[str]) -> Dict[str, Any]:
    """写同步请求 + 触发计划任务。running 未超时时拒绝重复触发。"""
    cur = status()
    if cur["status"] in ("running", "stale"):
        return {"ok": False, "reason": "sync_in_progress", "status": cur["status"]}

    valid = [s["id"] for s in SYSTEMS]
    picked = [s for s in systems if s in valid] or valid
    root = _root()
    root.mkdir(parents=True, exist_ok=True)
    req = {"systems": picked, "requested_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    (root / REQUEST_FILE).write_text(
        json.dumps(req, ensure_ascii=False), encoding="utf-8"
    )
    # 立即置 running，防止触发与 worker 启动之间的空窗重复提交
    state = {
        "status": "running", "started_at": req["requested_at"], "finished_at": None,
        "systems": picked, "summary": None, "systems_detail": [], "error": None,
    }
    (root / STATE_FILE).write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if not _task_installed():
        return {"ok": False, "reason": "task_not_installed", "status": "error",
                "hint": "先以本人身份运行 backend/scripts/install_prd_sync_task.ps1"}
    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", f"Start-ScheduledTask -TaskName '{TASK_NAME}'"],
            capture_output=True, text=True, timeout=20,
        )
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or "start_task_failed").strip()[:300])
    except Exception as exc:  # noqa: BLE001
        state.update(status="error", finished_at=req["requested_at"], error=f"trigger: {exc}")
        (root / STATE_FILE).write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return {"ok": False, "reason": "trigger_failed", "status": "error", "error": str(exc)}

    return {"ok": True, "status": "running", "systems": picked}
