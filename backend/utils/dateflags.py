"""共享日期标记工具：超期 / 临期 / 相对截止日状态。

把散落在 task_center / requirement 等处的"是否超期、是否临期"判断收敛到这里，
避免同一套语义在多处分头实现导致口径漂移。
"""

from datetime import date, datetime
from typing import Optional, Sequence, Tuple

DEFAULT_DUE_SOON_DAYS = 3
DEFAULT_WARNING_DAYS = 7
TERMINAL_STATUSES: Tuple[str, ...] = ("done", "blocked", "closed", "cancelled")


def _as_date(value) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


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
    return base <= due_d <= base + __import__("datetime").timedelta(days=window_days)


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
