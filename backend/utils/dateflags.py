"""共享日期标记工具：超期 / 临期 / 相对截止日状态。

把散落在 task_center / requirement 等处的"是否超期、是否临期"判断收敛到这里，
避免同一套语义在多处分头实现导致口径漂移。
"""

import re
from datetime import date, datetime, timedelta
from typing import Optional, Sequence, Tuple

DEFAULT_DUE_SOON_DAYS = 3
DEFAULT_WARNING_DAYS = 7
# 任务已历时告警阈值（天）：≥ 第一档标橙、≥ 第二档标红
DEFAULT_ELAPSED_WARN_DAYS = 30
DEFAULT_ELAPSED_ALERT_DAYS = 60
TERMINAL_STATUSES: Tuple[str, ...] = ("done", "blocked", "closed", "cancelled")


def _as_date(value) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def parse_loose_date(value) -> Optional[date]:
    """宽松解析日期 → date；解析不出返回 None。

    各来源表承载"创建时间"的字段格式不统一：可能是 date/datetime 对象，
    也可能是 "2026-07-01" / "2026/7/1" / "2026-07-01 10:30:00"。
    统一在此收敛，避免 task_center 与渲染层各写一套正则导致口径漂移。
    """
    d = _as_date(value)
    if d is not None:
        return d
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    m = re.match(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", s)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def days_since(start, today: Optional[date] = None) -> Optional[int]:
    """已历时天数（今天 - start）；未来日期归零，start 解析不出返回 None。"""
    d = parse_loose_date(start)
    if d is None:
        return None
    return max(0, ((today or date.today()) - d).days)


def is_overdue(due, today: Optional[date] = None, terminal_statuses: Sequence[str] = TERMINAL_STATUSES) -> bool:
    """截止日已过且未处于终态 → 超期。"""
    due_d = _as_date(due)
    if due_d is None:
        return False
    return due_d < (today or date.today())


def is_due_soon(
    due,
    today: Optional[date] = None,
    window_days: int = DEFAULT_DUE_SOON_DAYS,
    terminal_statuses: Sequence[str] = TERMINAL_STATUSES,
) -> bool:
    """截止日在 [今天, 今天+window] 内且未处于终态 → 临期。"""
    due_d = _as_date(due)
    if due_d is None:
        return False
    base = today or date.today()
    return base <= due_d <= base + timedelta(days=window_days)


def flag_due_date(
    due,
    status: Optional[str] = None,
    today: Optional[date] = None,
    due_soon_days: int = DEFAULT_DUE_SOON_DAYS,
    terminal_statuses: Sequence[str] = TERMINAL_STATUSES,
) -> dict:
    """返回 {is_overdue, is_due_soon}。终态直接视为未超期/未临期。"""
    if status in terminal_statuses:
        return {"is_overdue": False, "is_due_soon": False}
    return {
        "is_overdue": is_overdue(due, today, terminal_statuses),
        "is_due_soon": is_due_soon(due, today, due_soon_days, terminal_statuses),
    }


def relative_status(
    reference,
    today: Optional[date] = None,
    warning_days: int = DEFAULT_WARNING_DAYS,
    terminal_statuses: Sequence[str] = TERMINAL_STATUSES,
) -> str:
    """相对某参考截止日返回跟踪状态：overdue / warning / on_track。

    用于需求版本要求、开发工单等"未完成且相对截止日"的预警判断。
    已完成项的 late/on_time 语义由调用方另行处理。
    """
    ref_d = _as_date(reference)
    if ref_d is None:
        return "on_track"
    base = today or date.today()
    if base > ref_d:
        return "overdue"
    if 0 <= (ref_d - base).days <= warning_days:
        return "warning"
    return "on_track"
