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

# ── pb-2 候选池 ────────────────────────────────────────────────
TICKET_TYPES = (("req", "需求"), ("bug", "BUG"))
REQ_CLOSED_STATUSES = ("closed", "paused")          # 源需求：已上线 / 已暂停
BUG_CLOSED_STATUSES = ("resolved", "closed", "suspended")  # 源工单：已解决/已关闭/已挂起
BUG_CATEGORY_KEYS = ("bug",)                        # 问题大类=BUG（或子类 bug）
BUG_PRIORITY_KEYS = ("P0", "P1")
CANDIDATE_REASONS = (
    ("hit", "命中"),
    ("closed", "源状态已闭环"),
    ("no_anchor", "无版本锚点且无日期"),
    ("no_system", "无归属系统，进待补全"),
    ("excluded_type", "非 BUG / 咨询类工单"),
    ("already_tracked", "已有有效跟踪主行"),
    ("tombstone", "已被人工移出（墓碑行）"),
    ("source_missing", "源工单已删除"),
)

# ── pb-3 状态机 / 准入 / 结果 ───────────────────────────────────
ADMIT_STATUSES = (
    ("pending", "待判定"),
    ("admitted", "已准入"),
    ("not_admitted", "未准入（默认已顺延）"),
    ("exception", "人工例外准入"),
)
RESULTS = (
    ("", "未出结果"),
    ("live", "已上线"),
    ("not_scheduled", "未排进版本"),
    ("failed", "上线失败"),
    ("cancelled", "取消或撤回"),
)
TERMINAL_RESULTS = ("live", "cancelled")
DEFER_RESULTS = ("not_scheduled", "failed")
RESULT_REQUIRE_REASON = ("not_scheduled", "failed", "cancelled")
INCLUDE_SOURCES = (("pool", "候选池批量纳入"), ("inline", "工单行内纳入"), ("sync", "幂等同步"))
CHANGE_SOURCES = (
    ("page", "页面手工"), ("mail_feedback", "邮件反馈"), ("batch_update", "团队批量更新"),
    ("inline", "行内记一笔"), ("auto", "系统自动"), ("proxy", "代录"),
    ("manual_exception", "手工例外放行"),
)
STALL_DAYS = 7
NEAR_DUE_DAYS = 3
RESULT_CONFIRM_GRACE_DAYS = 3
DEFERRAL_FOCUS_MIN = 2
DEFERRAL_ABNORMAL_MIN = 3
NO_TEAM_LABEL = "（未分配团队）"

# ── pb-5 风险 ──────────────────────────────────────────────────
RISK_TYPES = (
    ("requirement_change", "需求变更"), ("plan_undecided", "方案未定"),
    ("dev_delay", "开发延期"), ("test_blocked", "测试阻塞"),
    ("env_dependency", "环境与依赖"), ("window_conflict", "发布窗口冲突"),
    ("admit_failed", "准入未通过"), ("go_live_failed", "上线失败"),
    ("resource", "资源不足"), ("stage_rollback", "环节回退"),
    ("deadline_overdue", "截止超期"), ("other", "其他"),
)
RISK_AUTO_TYPES = ("stage_rollback", "deadline_overdue", "go_live_failed", "admit_failed")
RISK_STATUSES = (("open", "未消除"), ("resolved", "已消除"), ("transferred", "已转顺延"))

# ── pb-6 督办 ──────────────────────────────────────────────────
COOLDOWN_HOURS = 24
EXCEPTION_RESEND_LIMIT = 2
SUPERVISE_INCLUDE_RULES = (
    ("overdue", "本环节截止日已超期且未完成"),
    ("near_due", "距本环节截止日 ≤3 天且未完成"),
    ("stalled", "当前环节停留 ≥7 天"),
    ("blocking_risk", "存在影响本版上线且未消除的风险"),
    ("wait_past_release", "等待发布但发布日已过、结果未登记"),
    ("rolled_back", "本环节发生回退且原因指向进度风险"),
    ("admit_pending", "准入待判定且距判定时点 ≤3 天仍未进入等待发布"),
    ("deferred", "本版顺延来的工单或顺延次数 ≥2"),
    ("receipt_overdue", "督办批次回执超时未回"),
)
SUPERVISE_EXCLUDE_RULES = (
    ("terminal", "已上线 / 已取消 / 已移出"),
    ("team_done", "该团队子行已完成本环节"),
    ("cooldown", "24h 冷却窗内已成功督办"),
    ("no_recipient", "收件人解析失败或邮箱无效"),
    ("suspended", "已批准挂起且原因已记录"),
    ("other_version", "非当前版本"),
    ("fresh_feedback", "已有有效反馈且给出可接受完成日、尚未到期"),
)
COOLDOWN_EXCEPTIONS = (
    ("risk_escalated", "风险等级升格或新增影响上线风险"),
    ("stage_rollback", "环节回退"),
    ("plan_changed", "版本发布日/计划/准入规则变更"),
    ("feedback_still_overdue", "收到厂家有效反馈但仍超期或完成日不可接受"),
    ("manual_ignore", "预览中显式勾选「忽略冷却」"),
)

# ── pb-7 反馈 ──────────────────────────────────────────────────
FEEDBACK_CHANNELS = (
    ("mail", "邮件回执"), ("batch", "团队批量更新"),
    ("inline", "行内记一笔"), ("proxy", "代录（电话·微信·会议）"),
)
FEEDBACK_STATUSES = (
    ("auto", "自动采纳"), ("pending", "待核对"), ("conflict", "冲突"),
    ("parse_failed", "解析失败"), ("rejected", "已驳回"),
)
RECEIPT_FIELDS = ("stage", "progress", "risk", "promise_date")
PENDING_RERUN_LABEL = "待自动补跑"

# ── pb-6/7 运行态展示字典（预览/批次/回执列转译，唯一源）────────
RECEIPT_STATUSES = (
    ("none", "无回执"), ("partial", "部分回执"),
    ("all", "全部回执"), ("overdue", "回执超时"),
)
SEND_STATUSES = (
    ("pending", "待发送"), ("sent", "已发送"), ("dry_run", "预览未发"),
    ("skipped", "已跳过"), ("failed", "发送失败"),
)
RISK_LEVELS = (("P0", "P0 紧急"), ("P1", "P1 高"), ("P2", "P2 中"), ("P3", "P3 低"))


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
        "ticket_types": [{"value": v, "label": l} for v, l in TICKET_TYPES],
        "admit_statuses": [{"value": v, "label": l} for v, l in ADMIT_STATUSES],
        "results": [{"value": v, "label": l} for v, l in RESULTS],
        "risk_types": [{"value": v, "label": l} for v, l in RISK_TYPES],
        "risk_statuses": [{"value": v, "label": l} for v, l in RISK_STATUSES],
        "risk_levels": [{"value": v, "label": l} for v, l in RISK_LEVELS],
        "receipt_statuses": [{"value": v, "label": l} for v, l in RECEIPT_STATUSES],
        "send_statuses": [{"value": v, "label": l} for v, l in SEND_STATUSES],
        "change_sources": [{"value": v, "label": l} for v, l in CHANGE_SOURCES],
        "feedback_channels": [{"value": v, "label": l} for v, l in FEEDBACK_CHANNELS],
        "feedback_statuses": [{"value": v, "label": l} for v, l in FEEDBACK_STATUSES],
        "supervise_include_rules": [{"value": v, "label": l} for v, l in SUPERVISE_INCLUDE_RULES],
        "supervise_exclude_rules": [{"value": v, "label": l} for v, l in SUPERVISE_EXCLUDE_RULES],
        "cooldown_exceptions": [{"value": v, "label": l} for v, l in COOLDOWN_EXCEPTIONS],
        "thresholds": {
            "stall_days": STALL_DAYS, "near_due_days": NEAR_DUE_DAYS,
            "cooldown_hours": COOLDOWN_HOURS, "deferral_focus_min": DEFERRAL_FOCUS_MIN,
            "deferral_abnormal_min": DEFERRAL_ABNORMAL_MIN,
            "result_confirm_grace_days": RESULT_CONFIRM_GRACE_DAYS,
        },
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
            "ticket_types": dict(TICKET_TYPES),
            "admit_statuses": dict(ADMIT_STATUSES),
            "results": dict(RESULTS),
            "risk_types": dict(RISK_TYPES),
            "risk_statuses": dict(RISK_STATUSES),
            "risk_levels": dict(RISK_LEVELS),
            "receipt_statuses": dict(RECEIPT_STATUSES),
            "send_statuses": dict(SEND_STATUSES),
            "change_sources": dict(CHANGE_SOURCES),
            "supervise_include_rules": dict(SUPERVISE_INCLUDE_RULES),
            "supervise_exclude_rules": dict(SUPERVISE_EXCLUDE_RULES),
            "cooldown_exceptions": dict(COOLDOWN_EXCEPTIONS),
            "feedback_channels": dict(FEEDBACK_CHANNELS),
            "feedback_statuses": dict(FEEDBACK_STATUSES),
        },
    }
