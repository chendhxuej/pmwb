"""工单 / 任务状态注册表 —— 全站状态定义的**唯一真相源**。

设计目标（对应「任务中心就地切换状态 + 工单状态标准化」方案）：
  1. 每类工单的状态集（原生态值 / 中文标签 / 语义色调 / 统一态 / 终态 / 流转规则）
     只在 **本文件** 声明一次，后端校验与前端展示全部由它派生。
  2. **支持后续新增状态定义**：新增一个状态 = 在本文件对应 domain 的 statuses 里加一个
     StatusDef；由于状态列已从 MySQL ENUM 改为 String(32)（迁移见 alembic），
     新增状态 **无需数据库迁移**，且下列横向触点自动兼容：
        - 后端：合法性校验 / to_unified 统一态映射 / 统计聚合 / 任务中心列表与详情
        - 前端：徽标 label+tone（StatusBadge）/ 筛选下拉 / 流转下拉可选目标 / 总览矩阵
        - 邮件：status_label 文案
  3. domain key 与前端 `constants/statusConfig.js` 里的 MODULE_STATUS / MODULE_SUBSTATUS
     key **一一对应**，前端 hydrate 后可直接覆盖本地 seed，杜绝「第二/第三份硬编码」。

严禁在本文件之外再写状态中文标签映射（历史事故：OwnerMatrix / 任务中心徽标
出现 pending / blocked 等英文原文，根因就是多份硬编码不同步）。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# ─────────────────────────────────────────────────────────────
# 统一态 bus（跨来源的四态，用于统计/矩阵/粗筛，稳定不易变）
# ─────────────────────────────────────────────────────────────
UNIFIED_STATUSES: Tuple[str, ...] = ("pending", "in_progress", "done", "blocked")
UNIFIED_LABELS: Dict[str, str] = {
    "pending": "待处理",
    "in_progress": "进行中",
    "done": "已完成",
    "blocked": "阻塞/挂起",
}


@dataclass(frozen=True)
class StatusDef:
    """单个状态定义。"""

    value: str                      # 源表原生状态值（写回 DB 的值，禁随意改）
    label: str                      # 中文标签（全站唯一文案源）
    tone: str                       # 语义色调：danger|warning|primary|success|info|neutral
    unified: str                    # 映射到的统一态（UNIFIED_STATUSES 之一）
    sensitive: bool = False         # 徽标脉冲高亮（逾期/待处理等需突出）
    is_terminal: bool = False       # 终态：默认不可逆，只能按 allowed_next 回退
    allowed_next: Tuple[str, ...] = ()   # 允许流转到的目标原生态值；()=无额外约束
    required_fields: Tuple[str, ...] = ()  # 进入该状态时源表必填列（责任人非空等）
    description: str = ""           # 说明（供前端 tooltip / 文档）


@dataclass(frozen=True)
class DomainDef:
    """一个状态域（对应前端一个 module key）。"""

    key: str                        # 域 key（= 前端 MODULE_STATUS/MODULE_SUBSTATUS key）
    label: str                      # 域显示名
    statuses: Tuple[StatusDef, ...] = ()
    writable: bool = True           # 是否允许就地改状态（派生只读域为 False）
    label_aliases: Dict[str, str] = field(default_factory=dict)  # 自由串容错别名
    description: str = ""


# ─────────────────────────────────────────────────────────────
# 各域状态定义
# ─────────────────────────────────────────────────────────────

_TODO = DomainDef(
    key="todo",
    label="个人待办",
    statuses=(
        StatusDef("todo", "未开始", "info", "pending", allowed_next=("in_progress", "done", "cancelled")),
        StatusDef("in_progress", "进行中", "primary", "in_progress", allowed_next=("done", "cancelled", "todo")),
        StatusDef("done", "已完成", "success", "done", is_terminal=True, allowed_next=("in_progress",)),
        StatusDef("cancelled", "已取消", "neutral", "blocked", is_terminal=True, allowed_next=("todo",)),
    ),
)

_OPERATION = DomainDef(
    key="operation",
    label="运营问题",
    statuses=(
        StatusDef("pending", "待处理", "danger", "pending", sensitive=True,
                  allowed_next=("processing", "suspended", "resolved", "closed")),
        StatusDef("processing", "处理中", "warning", "in_progress", required_fields=("handler",),
                  allowed_next=("verify", "resolved", "closed", "suspended", "pending")),
        StatusDef("verify", "验证中", "primary", "in_progress", required_fields=("handler",),
                  allowed_next=("resolved", "closed", "processing")),
        StatusDef("resolved", "已解决", "success", "done", is_terminal=True, required_fields=("handler",),
                  allowed_next=("closed", "processing")),
        StatusDef("closed", "已关闭", "info", "done", is_terminal=True, required_fields=("handler",),
                  allowed_next=("resolved",)),
        StatusDef("suspended", "已挂起", "neutral", "blocked",
                  allowed_next=("processing", "pending", "closed")),
    ),
)

_RESEARCH = DomainDef(
    key="research",
    label="一线调研",
    statuses=(
        StatusDef("pending", "待处理", "danger", "pending", sensitive=True,
                  allowed_next=("processing", "suspended", "resolved", "closed")),
        StatusDef("processing", "处理中", "warning", "in_progress", required_fields=("vendor_handlers",),
                  allowed_next=("verify", "resolved", "closed", "suspended", "pending")),
        StatusDef("verify", "验证中", "primary", "in_progress", required_fields=("vendor_handlers",),
                  allowed_next=("resolved", "closed", "processing")),
        StatusDef("resolved", "已解决", "success", "done", is_terminal=True, required_fields=("vendor_handlers",),
                  allowed_next=("closed", "processing")),
        StatusDef("closed", "已关闭", "info", "done", is_terminal=True, required_fields=("vendor_handlers",),
                  allowed_next=("resolved",)),
        StatusDef("suspended", "已挂起", "neutral", "blocked",
                  allowed_next=("processing", "pending", "closed")),
    ),
)

_TICKET = DomainDef(
    key="ticket",
    label="开发工单",
    statuses=(
        StatusDef("created", "已创建", "info", "pending", allowed_next=("design_reviewed",)),
        StatusDef("design_reviewed", "设计已评审", "primary", "in_progress",
                  allowed_next=("dev_completed", "created")),
        StatusDef("dev_completed", "开发完成", "warning", "in_progress",
                  allowed_next=("test_completed", "design_reviewed")),
        StatusDef("test_completed", "测试完成", "warning", "in_progress",
                  allowed_next=("live", "dev_completed")),
        StatusDef("live", "已上线", "success", "done", is_terminal=True,
                  allowed_next=("archived", "test_completed")),
        StatusDef("archived", "已归档", "neutral", "done", is_terminal=True, allowed_next=("live",)),
    ),
)

_MEETING_ACTION = DomainDef(
    key="meeting_action",
    label="会议行动项",
    statuses=(
        StatusDef("pending", "未开始", "info", "pending", sensitive=True,
                  allowed_next=("in_progress", "done", "not_attended")),
        StatusDef("in_progress", "进行中", "primary", "in_progress",
                  allowed_next=("done", "pending", "not_attended")),
        StatusDef("done", "已完成", "success", "done", is_terminal=True, allowed_next=("in_progress",)),
        StatusDef("not_attended", "未参会", "neutral", "pending", is_terminal=True,
                  allowed_next=("pending", "in_progress", "done")),
    ),
    # 该表 status 为 String(32) 自由串，历史数据可能是中文/别名，统一在此容错
    label_aliases={
        "": "pending",
        "待办": "pending",
        "待处理": "pending",
        "未开始": "pending",
        "doing": "in_progress",
        "进行中": "in_progress",
        "处理中": "in_progress",
        "已完成": "done",
        "完成": "done",
        "closed": "done",
        "已关闭": "done",
        "未参加": "not_attended",
        "缺席": "not_attended",
    },
)

_MEETING = DomainDef(
    key="meeting",
    label="会议",
    writable=False,   # 会议本身的状态在会议模块维护，任务中心不就地改
    statuses=(
        StatusDef("planned", "已计划", "info", "pending"),
        StatusDef("held", "已召开", "success", "done", is_terminal=True),
        StatusDef("cancelled", "已取消", "neutral", "blocked", is_terminal=True),
        StatusDef("not_attended", "未参会", "neutral", "blocked", is_terminal=True),
    ),
)

_KEYWORK_MAIN = DomainDef(
    key="keywork",
    label="重点工作",
    statuses=(
        StatusDef("planning", "规划中", "neutral", "pending",
                  allowed_next=("in_progress", "paused", "cancelled")),
        StatusDef("in_progress", "进行中", "primary", "in_progress",
                  allowed_next=("completed", "paused", "cancelled")),
        StatusDef("completed", "已完成", "success", "done", is_terminal=True, allowed_next=("in_progress",)),
        StatusDef("paused", "已暂停", "warning", "blocked", allowed_next=("in_progress", "cancelled")),
        StatusDef("cancelled", "已取消", "neutral", "blocked", is_terminal=True, allowed_next=("planning",)),
    ),
)

# 重点工作的三类子状态（里程碑 / 月周计划 / 成员待办）共用同一套五态
_KEYWORK_SUB_SCHEMA = (
    StatusDef("not_started", "未开始", "neutral", "pending",
              allowed_next=("in_progress", "completed", "delayed", "cancelled")),
    StatusDef("in_progress", "进行中", "primary", "in_progress",
              allowed_next=("completed", "delayed", "cancelled", "not_started")),
    StatusDef("delayed", "已延期", "danger", "blocked", sensitive=True,
              allowed_next=("in_progress", "completed", "cancelled")),
    StatusDef("completed", "已完成", "success", "done", is_terminal=True, allowed_next=("in_progress",)),
    StatusDef("cancelled", "已作废", "neutral", "blocked", is_terminal=True, allowed_next=("not_started",)),
)

_KEYWORK_MS = DomainDef(key="keywork_ms", label="重点工作·里程碑", statuses=_KEYWORK_SUB_SCHEMA)
_KEYWORK_PLAN = DomainDef(key="keywork_plan", label="重点工作·月周计划", statuses=_KEYWORK_SUB_SCHEMA)
_KEYWORK_TASK = DomainDef(key="keywork_task", label="重点工作·成员待办", statuses=_KEYWORK_SUB_SCHEMA)

_ACTIVE_OPTIMIZATION = DomainDef(
    key="active_optimization",
    label="主动优化",
    statuses=(
        StatusDef("pending", "待评估", "warning", "pending", allowed_next=("adopted", "rejected")),
        StatusDef("adopted", "已采纳", "success", "done", is_terminal=True, allowed_next=("pending",)),
        StatusDef("rejected", "不采纳", "neutral", "blocked", is_terminal=True, allowed_next=("pending",)),
    ),
)

_REQUIREMENT = DomainDef(
    key="requirement",
    label="需求",
    writable=False,   # 需求状态在需求模块维护
    statuses=(
        StatusDef("proposed", "建议中", "neutral", "pending"),
        StatusDef("accepted", "已受理", "primary", "in_progress"),
        StatusDef("dev", "开发中", "warning", "in_progress"),
        StatusDef("closed", "已上线", "success", "done", is_terminal=True),
        StatusDef("paused", "已暂停", "danger", "blocked", sensitive=True),
    ),
)

_REQUIREMENT_GROUP = DomainDef(
    key="requirement_group",
    label="需求分组",
    writable=False,
    statuses=(
        StatusDef("on_track", "进行中", "primary", "in_progress"),
        StatusDef("closed", "已关闭", "info", "done", is_terminal=True),
        StatusDef("paused", "已暂停", "danger", "blocked", sensitive=True),
    ),
)

_REQUIREMENT_DELIVERY = DomainDef(
    key="requirement_delivery",
    label="需求交付",
    writable=False,
    statuses=(
        StatusDef("proposed", "建议中", "neutral", "pending"),
        StatusDef("accepted", "已采纳", "primary", "in_progress"),
        StatusDef("dev", "开发中", "warning", "in_progress"),
        StatusDef("closed", "已上线", "success", "done", is_terminal=True),
        StatusDef("paused", "暂停", "warning", "blocked"),
    ),
)

_REQUIREMENT_VERSION = DomainDef(
    key="requirement_version",
    label="需求版本",
    writable=False,
    statuses=_TICKET.statuses,   # 与开发工单同构
)

# 任务中心统一态伪域（供前端 StatusBadge module="task_center" 使用，不可写）
_TASK_CENTER = DomainDef(
    key="task_center",
    label="任务中心（统一态）",
    writable=False,
    statuses=tuple(
        StatusDef(
            value=v,
            label=UNIFIED_LABELS[v],
            tone={"pending": "danger", "in_progress": "primary", "done": "success", "blocked": "neutral"}[v],
            unified=v,
            sensitive=(v == "pending"),
            is_terminal=(v in ("done", "blocked")),
        )
        for v in UNIFIED_STATUSES
    ),
)

# 需求催办：派生自 pmwb_requirement_evaluation（无 status 列），恒为待处理，只读
_REQUIREMENT_URGE = DomainDef(
    key="requirement_urge",
    label="需求催办",
    writable=False,
    statuses=(
        StatusDef("pending", "待处理", "warning", "pending", sensitive=True,
                  description="派生状态：团队评估未完成，非源表字段，不可修改"),
    ),
    # 该来源的任务列表 raw_status 由服务层填展示性伪值「待团队评估」（源表无 status 列），
    # 在此声明别名，保证任意来源的 raw_status 都能经 to_unified 解析到统一态。
    label_aliases={
        "": "pending",
        "待团队评估": "pending",
    },
)


# ─────────────────────────────────────────────────────────────
# 注册表本体
# ─────────────────────────────────────────────────────────────
REGISTRY: Dict[str, DomainDef] = {
    d.key: d
    for d in (
        _TODO,
        _OPERATION,
        _RESEARCH,
        _TICKET,
        _MEETING_ACTION,
        _MEETING,
        _KEYWORK_MAIN,
        _KEYWORK_MS,
        _KEYWORK_PLAN,
        _KEYWORK_TASK,
        _ACTIVE_OPTIMIZATION,
        _REQUIREMENT,
        _REQUIREMENT_GROUP,
        _REQUIREMENT_DELIVERY,
        _REQUIREMENT_VERSION,
        _TASK_CENTER,
        _REQUIREMENT_URGE,
    )
}

# 任务中心来源（source）→ 状态域（domain）映射。
# key_work 有多个子域，按 source_id 前缀二次解析。
SOURCE_DOMAIN: Dict[str, str] = {
    "todo": "todo",
    "operation_issue": "operation",
    "research_issue": "research",
    "dev_ticket": "ticket",
    "meeting_action": "meeting_action",
    "active_optimization": "active_optimization",
    "requirement_urge": "requirement_urge",
    "key_work": "keywork",   # 占位，实际由 _KEYWORK_PREFIX 解析
}

_KEYWORK_PREFIX: Dict[str, str] = {
    "task": "keywork_task",
    "milestone": "keywork_ms",
    "month": "keywork_plan",
    "week": "keywork_plan",
}


# ─────────────────────────────────────────────────────────────
# 查询 / 校验辅助函数
# ─────────────────────────────────────────────────────────────
def resolve_domain(source: str, source_id: str = "") -> str:
    """任务中心 source(+source_id) → 状态域 key。"""
    if source == "key_work":
        prefix = (source_id or "").split("-", 1)[0]
        return _KEYWORK_PREFIX.get(prefix, "keywork")
    return SOURCE_DOMAIN.get(source, source)


def get_domain(domain: str) -> Optional[DomainDef]:
    return REGISTRY.get(domain)


def get_status(domain: str, value: Optional[str]) -> Optional[StatusDef]:
    """取某域下的状态定义；先做别名容错再精确匹配。"""
    d = REGISTRY.get(domain)
    if not d:
        return None
    v = (value or "").strip()
    if v in d.label_aliases:
        v = d.label_aliases[v]
    for s in d.statuses:
        if s.value == v:
            return s
    return None


def to_unified(domain: str, value: Optional[str]) -> str:
    """原生态 → 统一态。未命中时兜底 pending（保留任务中心既有语义）。"""
    s = get_status(domain, value)
    return s.unified if s else "pending"


def allowed_next(domain: str, value: Optional[str]) -> List[str]:
    s = get_status(domain, value)
    return list(s.allowed_next) if s else []


def is_terminal(domain: str, value: Optional[str]) -> bool:
    s = get_status(domain, value)
    return bool(s and s.is_terminal)


def required_fields(domain: str, value: Optional[str]) -> List[str]:
    s = get_status(domain, value)
    return list(s.required_fields) if s else []


def is_writable(domain: str) -> bool:
    d = REGISTRY.get(domain)
    return bool(d and d.writable)


def labels_for(domain: str) -> Dict[str, str]:
    """{原生态值: 中文标签}，供前端/邮件生成中文映射。"""
    d = REGISTRY.get(domain)
    return {s.value: s.label for s in d.statuses} if d else {}


def domain_of_source(source: str, source_id: str = "") -> str:
    return resolve_domain(source, source_id)


def as_metadata() -> Dict[str, Any]:
    """序列化为前端元数据（hydrate 用）。结构对齐前端 MODULE_STATUS。"""
    domains: Dict[str, Any] = {}
    for key, d in REGISTRY.items():
        domains[key] = {
            "key": key,
            "label": d.label,
            "writable": d.writable,
            "description": d.description,
            # 自由串容错别名（历史脏值 → 规范值）。前端可用于「原值能否解析」的提示/校验。
            "label_aliases": dict(d.label_aliases),
            "statuses": [
                {
                    "value": s.value,
                    "label": s.label,
                    "tone": s.tone,
                    "unified": s.unified,
                    "sensitive": s.sensitive,
                    "is_terminal": s.is_terminal,
                    "allowed_next": list(s.allowed_next),
                    "required_fields": list(s.required_fields),
                    "description": s.description,
                }
                for s in d.statuses
            ],
        }
    return {
        "domains": domains,
        "unified_statuses": list(UNIFIED_STATUSES),
        "unified_labels": dict(UNIFIED_LABELS),
        "source_domain": dict(SOURCE_DOMAIN),
        "keywork_prefix": dict(_KEYWORK_PREFIX),
    }
