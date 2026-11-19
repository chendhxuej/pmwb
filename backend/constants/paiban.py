"""排版管理（PB）常量 —— 枚举 / 倒排偏移 / 准入规则的**唯一真相源**。

决策回填 v1.2（2026-11-18 老大拍板）：
  - 四环节倒排偏移固定 −15 / −8 / −3 / −1 个自然日（相对计划发布日）；
  - CRM 需提前 7 个自然日进入「等待发布」才准入；未准入**默认自动顺延**，
    确需留本版只走单据级「手工例外放行」（原因/操作人/时间/原判定事实四要素）；
  - 本期不做部分上线、不接任务中心、不回写运营 BUG 工单。

严禁在其它文件另写中文标签映射或第二份倒排公式；前端一律从 /paiban/meta 取。
"""

from datetime import date, timedelta

# ── 四环节（顺序即推进顺序）─────────────────────────────────────
STAGES = (
    ("plan_confirm", "方案确认中"),
    ("dev", "开发中"),
    ("test", "测试中"),
    ("wait_release", "等待发布"),
)
STAGE_LABELS = dict(STAGES)

# 发布日倒排偏移（决策 #2，不得在别处复制）
STAGE_DEADLINE_OFFSETS = {
    "plan_confirm": -15,
    "dev": -8,
    "test": -3,
    "wait_release": -1,
}
FREEZE_OFFSET_DAYS = -15  # 需求/方案冻结日 = 发布日 −15

# ── 版本计划字典 ──────────────────────────────────────────────
SCOPE_TYPES = (("default", "统一默认"), ("system", "指定系统"))
VERSION_TYPES = (
    ("regular", "常规版"),
    ("emergency", "紧急补丁"),
    ("ad_hoc", "临时加版"),
)
PLAN_STATUSES = (
    ("draft", "拟定"),
    ("confirmed", "已确认"),
    ("published", "已发布"),
    ("closed", "已收口"),
    ("cancelled", "已取消"),
)
# 有效计划（可回落 / 可作顺延目标）；「已收口」触发顺延判定但不再接收新工单
ACTIVE_PLAN_STATUSES = ("draft", "confirmed", "published")
TERMINAL_PLAN_STATUSES = ("closed", "cancelled")

ADMIT_MODES = (
    ("open", "开放（无提前准入闸门）"),
    ("wait_release_n_days", "提前 N 天进入等待发布才准入"),
)
DEFAULT_ADMIT_LEAD_DAYS = 7  # 决策 #3：CRM 提前 7 个自然日
CRM_SYSTEM_KEY = "CRM"       # 系统名来自人员中台字典，精确匹配，禁 LIKE 硬凑

# 单据级手工例外放行原因闭集（pb-3 使用；其它需填说明）
EXCEPTION_REASONS = (
    ("customer_hard_deadline", "客户/集团硬性时间要求"),
    ("production_fix", "生产故障修复须随本版"),
    ("upstream_ready", "上游依赖已在本版就绪"),
    ("window_changed", "版本窗口调整导致判定时点变化"),
    ("other", "其他（须填写说明）"),
)

# 变更日志留痕字段（改任一项必须写一条）
WATCHED_FIELDS = (
    "release_date", "status", "admit_mode", "admit_lead_days",
    "allow_temp_merge", "next_version_id",
)


def _iso(d: date) -> str:
    return d.isoformat() if isinstance(d, date) else ""


def derive_deadlines(release_date: date) -> dict:
    """由计划发布日**唯一派生**冻结日 + 四环节截止，不落库、不逐单手填。

    默认计划改期时所有回落工单的截止日由此自动同步重算。
    """
    if not isinstance(release_date, date):
        raise ValueError("release_date 必须是 date")
    stages = []
    for key, label in STAGES:
        offset = STAGE_DEADLINE_OFFSETS[key]
        stages.append({
            "key": key,
            "label": label,
            "offset_days": offset,
            "deadline": _iso(release_date + timedelta(days=offset)),
        })
    return {
        "release_date": _iso(release_date),
        "freeze_date": _iso(release_date + timedelta(days=FREEZE_OFFSET_DAYS)),
        "stages": stages,
    }


def admit_gate_at(release_date: date, admit_mode: str, admit_lead_days: int) -> str:
    """准入判定时点 = 计划发布日 − N 天；开放模式无闸门（返回空串）。"""
    if admit_mode != "wait_release_n_days":
        return ""
    if not isinstance(release_date, date):
        raise ValueError("release_date 必须是 date")
    n = int(admit_lead_days or 0)
    if n <= 0:
        raise ValueError("提前准入天数必须大于 0")
    return _iso(release_date - timedelta(days=n))


def preset_for_system(system_name: str) -> dict:
    """按系统给出版本计划准入默认值（CRM 特殊；其余开放）。

    只作为登记页的**带出值**，不是第二份规则：实际判定一律读已落库的版本计划。
    """
    if (system_name or "").strip() == CRM_SYSTEM_KEY:
        return {
            "admit_mode": "wait_release_n_days",
            "admit_lead_days": DEFAULT_ADMIT_LEAD_DAYS,
            "allow_temp_merge": 0,
            "is_crm": True,
        }
    return {
        "admit_mode": "open",
        "admit_lead_days": 0,
        "allow_temp_merge": 1,
        "is_crm": False,
    }


def meta_payload(system_options: list, dict_degraded: bool) -> dict:
    """GET /paiban/meta 的唯一组包口径。"""
    return {
        "stages": [{"key": k, "label": v, "offset_days": STAGE_DEADLINE_OFFSETS[k]} for k, v in STAGES],
        "freeze_offset_days": FREEZE_OFFSET_DAYS,
        "scope_types": [{"value": v, "label": l} for v, l in SCOPE_TYPES],
        "version_types": [{"value": v, "label": l} for v, l in VERSION_TYPES],
        "plan_statuses": [{"value": v, "label": l} for v, l in PLAN_STATUSES],
        "admit_modes": [{"value": v, "label": l} for v, l in ADMIT_MODES],
        "exception_reasons": [{"value": v, "label": l} for v, l in EXCEPTION_REASONS],
        "default_admit_lead_days": DEFAULT_ADMIT_LEAD_DAYS,
        "crm_system_key": CRM_SYSTEM_KEY,
        "system_options": system_options,
        "dict_degraded": dict_degraded,
        "labels": {
            "scope_types": dict(SCOPE_TYPES),
            "version_types": dict(VERSION_TYPES),
            "plan_statuses": dict(PLAN_STATUSES),
            "admit_modes": dict(ADMIT_MODES),
            "stages": STAGE_LABELS,
        },
    }
