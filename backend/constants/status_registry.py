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
    free_transition: bool = False   # True=该域任意状态互转，忽略各 StatusDef 的 allowed_next
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
        StatusDef("proposed", "建议中", "neutral", "pending",
                  allowed_next=("accepted", "dev", "closed", "paused")),
        StatusDef("accepted", "已受理", "primary", "in_progress",
                  allowed_next=("dev", "closed")),
        StatusDef("dev", "开发中", "warning", "in_progress",
                  allowed_next=("partial_live", "live_failed", "closed", "paused")),
        StatusDef("partial_live", "部分上线", "warning", "in_progress",
                  allowed_next=("closed", "live_failed", "dev")),
        StatusDef("live_failed", "上线失败", "danger", "blocked", sensitive=True,
                  allowed_next=("dev", "paused")),
        StatusDef("closed", "已上线", "success", "done", is_terminal=True),
        StatusDef("paused", "已暂停", "danger", "blocked", sensitive=True,
                  allowed_next=("proposed", "accepted", "dev")),
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

# 高级别工单的**本地跟踪态**（2026-10-15 新增，任务中心「高级别工单」子模块）。
# 注意：这不是源工单状态，而是跟踪表 pmwb_high_level_track.track_status 的取值集合；
# 源工单状态仍由各来源域（operation/ticket/...）负责。
# 刻意 **不加入 SOURCE_DOMAIN**：它不对应任何 TASK_SOURCES 来源，
# 加入会污染任务中心「来源→状态域」映射与统一态统计。
_HIGH_LEVEL_TRACK = DomainDef(
    key="high_level_track",
    label="高级别工单·跟踪",
    writable=True,
    statuses=(
        StatusDef("open", "待跟进", "info", "pending",
                  allowed_next=("tracking", "escalated", "resolved", "dropped"),
                  description="首次纳入、尚未开始跟踪"),
        StatusDef("tracking", "跟踪中", "primary", "in_progress",
                  allowed_next=("escalated", "resolved", "dropped", "open"),
                  description="已开始跟踪推进"),
        StatusDef("escalated", "已升级", "warning", "in_progress", sensitive=True,
                  allowed_next=("resolved", "dropped", "tracking"),
                  description="已升级/已督办，需重点关注"),
        StatusDef("resolved", "已闭环", "success", "done", is_terminal=True,
                  allowed_next=("tracking",),
                  description="源工单已达终态或人工确认闭环"),
        StatusDef("dropped", "已移除", "neutral", "blocked", is_terminal=True,
                  allowed_next=("open",),
                  description="源工单消失或人工移出跟踪范围"),
    ),
    description="高级别工单本地跟踪态（非源工单状态；源状态见各来源域）",
)

# 需求×厂家 的开发状态（2026-10-16 新增，生产部署环节「厂家开发状态」卡片）。
# 落地表 pmwb_req_vendor_dev.dev_status。
# 刻意 **不加入 SOURCE_DOMAIN**：它不是任务中心的「来源」，加入会污染
# 任务中心「来源→状态域」映射与统一态统计（理由同 high_level_track）。
# 关键语义：live（已上线）由插件自动置位，completed（已完成）由人工确认；
# 需求级「上线联动」只看 completed，不看 live。
#
# 2026-10-21 调整（老大要求）：
#   1) 枚举值向需求工单状态（requirement 域）看齐，补齐 partial_live / live_failed /
#      paused 三态 —— 厂家维度确实会出现「只上了一部分」「上线失败回滚」「暂停开发」，
#      原先只有 4 态时只能瞎选一个，台账失真。
#      requirement 的 proposed/accepted（建议中/已受理）不加：厂家行由需求派生，
#      需求没受理时根本不会有厂家行。
#   2) **free_transition=True 放开流转限制**：页面上下拉可选全部状态、任意互转
#      （含 completed 退回），后端不再以 allowed_next 拦截。
#      原因：厂家实际操作顺序不受系统预设约束（例：上线后发现问题→回滚到开发中→
#      再上线），硬拦只会逼人去错填别的状态。
_VENDOR_DEV = DomainDef(
    key="vendor_dev",
    label="厂家开发状态",
    writable=True,
    free_transition=True,   # ★ 任意状态互转，见上方说明
    statuses=(
        StatusDef("pending", "待开发", "info", "pending",
                  description="厂家尚未启动开发"),
        StatusDef("developing", "开发中", "primary", "in_progress",
                  description="厂家开发中；插件漏抓时可直接确认完成"),
        StatusDef("partial_live", "部分上线", "warning", "in_progress",
                  description="该厂家只交付了部分功能/模块，其余仍在开发或待上线"),
        StatusDef("live", "已上线", "success", "in_progress", sensitive=True,
                  description="插件抓到厂家开发单「已上线待需求录入人确认」后自动置此态，仍需人工确认完成"),
        StatusDef("live_failed", "上线失败", "danger", "blocked", sensitive=True,
                  description="上线过程失败/回滚，需厂家重新排期"),
        StatusDef("paused", "已暂停", "danger", "blocked", sensitive=True,
                  description="厂家暂停该需求的开发（排期调整、需求方叫停等）"),
        StatusDef("completed", "已完成", "success", "done", is_terminal=True,
                  description="人工确认该厂家开发完成；最后一家置此态时触发需求级上线联动"),
    ),
    # dev_status 为 String(32) 自由串，历史/外部值容错
    label_aliases={
        "": "developing",
        "待开发": "pending",
        "未开发": "pending",
        "开发中": "developing",
        "上线": "live",
        "已上线": "live",
        "部分上线": "partial_live",
        "上线失败": "live_failed",
        "暂停": "paused",
        "已暂停": "paused",
        "完成": "completed",
        "已完成": "completed",
    },
    description="需求×厂家开发状态（生产部署）；厂家清单=团队评估中 workload>0 的系统；状态任意互转",
)

# 敏感需求跟踪态（2026-10-25 新增，需求与交付「敏感需求跟踪」子模块）。
# 与 _HIGH_LEVEL_TRACK 同构：不是源需求状态，而是跟踪表
# pmwb_sensitive_req_track.track_status 的取值集合；源需求状态仍由 requirement 域负责。
# 刻意 **不加入 SOURCE_DOMAIN**（理由同 high_level_track）；
# 任务中心 collector（source=sensitive_req）在服务层用本域做统一态映射。
_SENSITIVE_REQ_TRACK = DomainDef(
    key="sensitive_req_track",
    label="敏感需求·跟踪",
    writable=True,
    statuses=(
        StatusDef("active", "跟踪中", "primary", "in_progress",
                  allowed_next=("delayed", "escalated", "resolved", "dropped"),
                  description="已纳入倒排跟踪"),
        StatusDef("delayed", "已逾期", "warning", "in_progress", sensitive=True,
                  allowed_next=("escalated", "resolved", "dropped", "active"),
                  description="存在里程碑超期未完成"),
        StatusDef("escalated", "督办升级", "danger", "in_progress", sensitive=True,
                  allowed_next=("resolved", "dropped", "active", "delayed"),
                  description="已邮件督办/人工提级，需重点关注"),
        StatusDef("resolved", "已上线闭环", "success", "done", is_terminal=True,
                  allowed_next=("active",),
                  description="需求已上线或人工确认闭环"),
        StatusDef("dropped", "已移除", "neutral", "blocked", is_terminal=True,
                  allowed_next=("active",),
                  description="源需求消失、级别下调或人工移出跟踪范围"),
    ),
    description="敏感需求本地跟踪态（非源需求状态；源状态见 requirement 域）",
)

# 敏感需求里程碑状态（2026-10-25 新增）：pmwb_sensitive_req_milestone.status。
# 同样不加入 SOURCE_DOMAIN（非任务来源域）。
_SENSITIVE_MILESTONE = DomainDef(
    key="sensitive_milestone",
    label="敏感需求·里程碑",
    writable=True,
    free_transition=True,   # 实际推进顺序不受系统预设约束（补录/回退常态），任意互转
    statuses=(
        StatusDef("pending", "未开始", "info", "pending",
                  description="阶段未启动"),
        StatusDef("doing", "进行中", "primary", "in_progress",
                  description="阶段推进中"),
        StatusDef("done", "已完成", "success", "done", is_terminal=True,
                  description="阶段工作完成（actual_end 已填或以此为准）"),
    ),
    label_aliases={
        "": "pending",
        "未开始": "pending",
        "进行中": "doing",
        "已完成": "done",
        "完成": "done",
    },
    description="敏感需求里程碑状态（需求×团队×阶段）；任意互转",
)


# ─────────────────────────────────────────────────────────────
# 注册表本体
# ─────────────────────────────────────────────────────────────
_COMPLAINT_ACTION = DomainDef(
    key="complaint_action",
    label="客诉改进措施",
    statuses=(
        StatusDef("planned", "待启动", "info", "pending",
                  allowed_next=("in_progress", "cancelled")),
        StatusDef("in_progress", "推进中", "warning", "in_progress", required_fields=("owner",),
                  allowed_next=("verifying", "cancelled", "planned")),
        StatusDef("verifying", "验证中", "primary", "in_progress", required_fields=("owner", "go_live_date"),
                  allowed_next=("effective", "ineffective", "in_progress")),
        StatusDef("effective", "已验证有效", "success", "done", is_terminal=True,
                  allowed_next=("verifying",)),
        StatusDef("ineffective", "验证未达标", "danger", "blocked",
                  allowed_next=("in_progress", "cancelled")),
        StatusDef("cancelled", "已取消", "neutral", "blocked", is_terminal=True,
                  allowed_next=("planned",)),
    ),
    label_aliases={
        "": "planned",
        "待启动": "planned",
        "推进中": "in_progress",
        "验证中": "verifying",
        "已验证有效": "effective",
        "验证未达标": "ineffective",
        "已取消": "cancelled",
    },
    description="客诉改进措施台账状态：planned→in_progress→verifying→effective/ineffective",
)

_COMPLAINT_PROBLEM = DomainDef(
    key="complaint_problem",
    label="客诉共性问题",
    statuses=(
        StatusDef("candidate", "待确认", "info", "pending",
                  allowed_next=("open", "ignored", "merged")),
        StatusDef("open", "待处置", "danger", "pending", required_fields=("owner",),
                  allowed_next=("resolving", "closed", "ignored")),
        StatusDef("resolving", "闭环推进中", "primary", "in_progress", required_fields=("owner",),
                  allowed_next=("closed", "open", "ignored")),
        StatusDef("closed", "已闭环", "success", "done", is_terminal=True,
                  required_fields=("conclusion",),
                  allowed_next=("resolving",)),  # 复发重开必经推进态（重新挂措施）
        StatusDef("ignored", "已忽略", "neutral", "blocked", is_terminal=True,
                  allowed_next=("open",)),  # 可反悔
        StatusDef("merged", "已合并", "neutral", "blocked", is_terminal=True,
                  allowed_next=()),
    ),
    label_aliases={
        "": "candidate",
        "待确认": "candidate",
        "待处置": "open",
        "闭环推进中": "resolving",
        "已闭环": "closed",
        "已忽略": "ignored",
        "已合并": "merged",
    },
    description="客诉共性问题台账：candidate→open→resolving→closed；复发 closed→resolving 重开。"
                "不入任务中心（可执行单元是措施），故不加入 SOURCE_DOMAIN",
)


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
        _HIGH_LEVEL_TRACK,
        _VENDOR_DEV,
        _SENSITIVE_REQ_TRACK,
        _SENSITIVE_MILESTONE,
        _COMPLAINT_ACTION,
        _COMPLAINT_PROBLEM,
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
    # 2026-10-25：敏感需求任务来源 → 本地跟踪态域（raw_status=track_status）
    "sensitive_req": "sensitive_req_track",
    # 2026-10-27：客诉改进措施 → 措施台账状态域
    "complaint_action": "complaint_action",
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
    """可流转到的目标状态值列表。

    - 域标记 ``free_transition=True``（如 vendor_dev）：返回该域**全部其他状态**，
      即任意互转；调用方的「不在白名单就拒绝」校验自然放行。
    - 否则按 StatusDef.allowed_next 返回；``()`` 表示无额外约束（由调用方决定）。
    """
    d = REGISTRY.get(domain)
    if not d:
        return []
    cur = get_status(domain, value)
    if d.free_transition:
        cur_value = cur.value if cur else (value or "").strip()
        return [s.value for s in d.statuses if s.value != cur_value]
    return list(cur.allowed_next) if cur else []


def is_free_transition(domain: str) -> bool:
    """该域是否放开流转限制（任意状态互转）。"""
    d = REGISTRY.get(domain)
    return bool(d and d.free_transition)


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
            "free_transition": d.free_transition,
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
                    # free_transition 域下发全集，避免前端拿到 () 后误判「无处可去」
                    "allowed_next": allowed_next(key, s.value),
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
