"""PRD 知识同步 worker —— 以老大用户身份(chend)由 Windows 计划任务触发。

职责：读后端写入的同步请求 → 调用 skill 的 init_knowledge.py（GCM 凭据在用户态）
      → 把结果写回状态文件供后端 LocalSystem 轮询。服务端零凭据。

只会同步 registry 中 enabled 的系统；--system 参数由请求指定（白名单校验）。
请求/状态文件均在 D:\\项目\\knowledge\\ 下，与知识 clone 同根目录。
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

ROOT = Path("D:/项目")
KNOWLEDGE = ROOT / "knowledge"
REQUEST_FILE = KNOWLEDGE / ".sync_request.json"
STATE_FILE = KNOWLEDGE / ".sync_state.json"
LOG_FILE = KNOWLEDGE / "sync.log"
INIT_SCRIPT = Path(
    "C:/Users/chend/Desktop/需求分析skills/prd-workflow-init/"
    "prd-workflow-init/scripts/init_knowledge.py"
)
ALLOWED_SYSTEMS = {"CRM", "BOSS", "ORDER_CENTER"}


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _write_state(state: Dict[str, Any]) -> None:
    KNOWLEDGE.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _log(msg: str) -> None:
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(f"[{_now()}] {msg}\n")
    except OSError:
        pass


def main() -> int:
    state: Dict[str, Any] = {
        "status": "running",
        "started_at": _now(),
        "finished_at": None,
        "systems": [],
        "summary": None,
        "systems_detail": [],
        "error": None,
    }
    _write_state(state)

    if not REQUEST_FILE.is_file():
        state.update(status="error", finished_at=_now(), error="no_request")
        _write_state(state)
        _log("error: no_request")
        return 1

    try:
        req = json.loads(REQUEST_FILE.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        state.update(status="error", finished_at=_now(), error=f"bad_request: {exc}")
        _write_state(state)
        _log(f"error: bad_request {exc}")
        return 1

    systems = [s for s in req.get("systems", []) if s in ALLOWED_SYSTEMS]
    if not systems:
        systems = ["CRM", "BOSS", "ORDER_CENTER"]
    state["systems"] = systems
    _write_state(state)

    cmd = [sys.executable, str(INIT_SCRIPT), "--root", str(ROOT), "--timeout", "900"]
    for s in systems:
        cmd += ["--system", s]
    _log("run: " + " ".join(cmd))

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=1200, cwd=str(ROOT)
        )
        out = (proc.stdout or "").strip()
        err = (proc.stderr or "").strip()
        _log(f"exit={proc.returncode} stderr={err[:300]}")
        result: Dict[str, Any] = {}
        # init 脚本 stdout 是单个 JSON；若夹杂 git 进度行，取最后一个 { 开头的可解析块
        for line in reversed(out.splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    result = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue
        if not result:
            # 整体尝试（多行 JSON）
            try:
                result = json.loads(out)
            except json.JSONDecodeError:
                result = {}

        detail = result.get("systems", [])
        summary = result.get("summary", {})
        state.update(
            systems_detail=detail,
            summary=summary,
            finished_at=_now(),
            status="ok" if result.get("status") == "ok" and proc.returncode == 0 else "error",
            error=None if result.get("status") == "ok" and proc.returncode == 0
            else (err[:500] or result.get("reason") or "sync_failed"),
        )
        # 同步成功：记录同步时间（供页面显示）
        if state["status"] == "ok":
            state["synced_at"] = result.get("generated_at") or _now()
    except subprocess.TimeoutExpired:
        state.update(status="error", finished_at=_now(), error="timeout")
        _log("error: timeout")
    except Exception as exc:  # noqa: BLE001
        state.update(status="error", finished_at=_now(), error=f"worker: {exc}")
        _log(f"error: worker {exc}")

    _write_state(state)
    # 消费请求，避免重复触发
    try:
        REQUEST_FILE.unlink(missing_ok=True)
    except OSError:
        pass
    return 0 if state["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
