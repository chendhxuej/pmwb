"""客诉根因枚举 —— 根因层（L1）与根因库（L2）字段取值的**唯一真相源**。

背景（2026-11-03 老大拍板「客诉专题优化」）：
  原 30 个二级「现象场景」承载 228 单，最大桶 38 单混装 6 类不相关问题，
  AI 归类置信度 <0.85 占 71%。根因识别是批量投诉识别与解决方案制定的基础数据，
  故将「分类打标」升级为「根因归纳 + 自下而上建库」，本文件定义根因维度的受控枚举。

设计原则（对齐 status_registry / 单一真相源铁律）：
  1. 枚举只在此声明一次；后端校验、LLM prompt、前端下拉、统计聚合全部由本文件派生；
  2. 落库值即中文名（零转译，同 pmwb_meeting_type / requirement_category）；
  3. **新增一枚枚举 = 本文件加一行**（数据库列为 String，无需迁移）；
  4. 严禁在 prompt 文本、前端组件、脚本里另写第二份枚举清单。

维度含义：
  fault_stage   故障发生在业务链的哪一环（用于「环节漏斗」分析，定位改造落点）
  fault_system  涉及哪个系统（用于责任归属与研发分工）
  fault_type    缺陷性质（区分「要不要改代码」）
  own_party     责任归属（区分「谁该修」）
  fix_mode      处置方式（区分「能不能一次消灭」）
  repro         可复现性（可复现=批量修复收益高；不可复现=先加日志/监控）
"""

from typing import Dict, List, Tuple

# ── 故障环节（业务链顺序排列，前端漏斗图直接用此序）────────────────
FAULT_STAGES: Tuple[str, ...] = (
    "前台受理",     # 客户经理/营业厅提单、选品、填单
    "协议签约",     # 电子协议生成、盖章、二次转单
    "订单开通",     # 订单中心建单、派单、施工单下发
    "业务激活",     # 宽带/电视/增值包激活与校验
    "数据同步",     # 跨系统数据（CRM/BOSS/CMIOT/电视平台）同步
    "计费出账",     # 出账、折后、优惠、退费
    "产品配置",     # 产品/营销案/权限配置
    "装维交付",     # 上门施工、安装、现场交付
    "账务结算",     # 账单争议、发票、欠费复机
    "使用咨询",     # 使用操作、功能咨询（非缺陷）
    "其他",
)

# ── 涉及系统 ─────────────────────────────────────────────────
FAULT_SYSTEMS: Tuple[str, ...] = (
    "CRM",
    "BOSS",
    "订单中心",
    "政企工作台",
    "电子协议",
    "CMIOT",
    "电视平台",
    "计费系统",
    "短信平台",
    "第三方厂家系统",
    "无",           # 非系统问题（流程/操作/认知）
)

# ── 缺陷性质 ─────────────────────────────────────────────────
FAULT_TYPES: Tuple[str, ...] = (
    "代码缺陷",     # 功能逻辑错误，需研发改代码
    "接口映射错",   # 字段映射/参数/枚举转换错误
    "数据不同步",   # 跨系统状态、账号、订购关系未同步
    "数据脏污",     # 存量数据错误、串号、残留
    "配置缺失",     # 产品/权限/参数未配置或配错
    "规则不合理",   # 业务规则或流程设计不合理
    "权限缺失",     # 账号/角色权限不足导致操作不了
    "容量性能",     # 超时、并发、性能瓶颈
    "无缺陷",       # 咨询解释类，系统与流程均正常
    "待核实",       # 信息不足，无法判定
)

# ── 责任归属 ─────────────────────────────────────────────────
OWN_PARTIES: Tuple[str, ...] = (
    "系统研发",     # 需研发修复
    "流程规则",     # 需流程/规则改造
    "数据治理",     # 需存量数据批量清理
    "一线操作",     # 前端操作不规范，需培训/校验前置
    "客户认知",     # 客户理解偏差，需解释指引
    "第三方厂家",   # 厂家侧问题，需协同
    "待核实",
)

# ── 处置方式 ─────────────────────────────────────────────────
FIX_MODES: Tuple[str, ...] = (
    "批量修复",     # 一次脚本/同步可消掉存量同类单
    "系统改造",     # 需版本迭代
    "规则调整",     # 改流程/规则/配置即可
    "逐单处理",     # 只能单笔处理，无共性可修
    "解释指引",     # 补操作指引/知识库，消解咨询类
)

# ── 可复现性 ─────────────────────────────────────────────────
REPRO_VALUES: Tuple[str, ...] = ("yes", "no", "unknown")
REPRO_LABELS: Dict[str, str] = {
    "yes": "可复现",
    "no": "不可复现",
    "unknown": "未确认",
}

# ── 根因状态（写 pmwb_complaint_ticket.rc_status）────────────
RC_STATUS_PENDING = ""        # 待分析
RC_STATUS_AI = "ai"           # 已归纳（过质量门禁）
RC_STATUS_LOW = "low"         # 待人工（门禁未过或置信度不足）
RC_STATUS_MANUAL = "manual"   # 人工确认（重跑永不覆盖）

RC_STATUS_LABELS: Dict[str, str] = {
    RC_STATUS_PENDING: "待分析",
    RC_STATUS_AI: "已归纳",
    RC_STATUS_LOW: "待人工",
    RC_STATUS_MANUAL: "人工确认",
}

# ── 根因库状态（写 pmwb_complaint_rootcause.status）──────────
RC_LIB_CANDIDATE = "candidate"
RC_LIB_OPEN = "open"
RC_LIB_MERGED = "merged"
RC_LIB_DISABLED = "disabled"

RC_LIB_STATUS_LABELS: Dict[str, str] = {
    RC_LIB_CANDIDATE: "待确认",
    RC_LIB_OPEN: "已入账",
    RC_LIB_MERGED: "已合并",
    RC_LIB_DISABLED: "已停用",
}

# ── 根因描述质量门禁（泛词黑名单，防再次"泛化"）────────────────
# 命中这些词说明根因停在「现象层」，没有落到真实问题点。
GENERIC_TERMS: Tuple[str, ...] = (
    "操作咨询", "操作指引", "系统问题", "数据问题", "流程优化", "投诉咨询",
    "数据不一致", "状态不一致", "需要核实", "需核实", "待核实", "存在问题",
    "出现异常", "发生异常", "系统异常", "数据异常", "处理中", "已解决",
    "已处理", "协助处理", "请协助", "无法处理", "报错", "失败",
)

# 根因描述最小有效字数（剔除泛词后仍需 >= 此值，才算"说到点子上"）
RC_MIN_EFFECTIVE_CHARS = 20
# 根因描述总最小字数
RC_MIN_TOTAL_CHARS = 25


def fault_stage_options() -> List[str]:
    return list(FAULT_STAGES)


def fault_system_options() -> List[str]:
    return list(FAULT_SYSTEMS)


def fault_type_options() -> List[str]:
    return list(FAULT_TYPES)


def own_party_options() -> List[str]:
    return list(OWN_PARTIES)


def fix_mode_options() -> List[str]:
    return list(FIX_MODES)


def enum_meta() -> Dict[str, object]:
    """前端 /meta 端点统一导出（根因枚举唯一出口）。"""
    return {
        "fault_stages": fault_stage_options(),
        "fault_systems": fault_system_options(),
        "fault_types": fault_type_options(),
        "own_parties": own_party_options(),
        "fix_modes": fix_mode_options(),
        "repros": [{"value": v, "label": REPRO_LABELS[v]} for v in REPRO_VALUES],
        "rc_statuses": [{"value": k, "label": v} for k, v in RC_STATUS_LABELS.items()],
        "rc_lib_statuses": [{"value": k, "label": v} for k, v in RC_LIB_STATUS_LABELS.items()],
        "generic_terms": list(GENERIC_TERMS),
    }


def normalize_choice(value: str, options: Tuple[str, ...]) -> str:
    """把 LLM 输出对齐到受控枚举：精确命中优先，其次包含匹配，否则返回空串（不编造）。"""
    v = (value or "").strip()
    if not v:
        return ""
    if v in options:
        return v
    for o in options:
        if o in v or v in o:
            return o
    return ""
