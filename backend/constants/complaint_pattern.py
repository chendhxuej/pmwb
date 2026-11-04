"""客诉根因模式（L2 簇键）受控枚举 —— 机制 / 业务对象 / 触发条件的**唯一真相源**。

背景（2026-11-04 老大拍板「根因簇识别不应涉及用户级信息，按系统、产品、服务场景、
订单环节、业务功能使用场景汇聚；本期簇数 ≤100」）：
  实测 858 个有效簇里 776 个是「1 单 1 簇」（90.4%），但标题带 ≥6 位数字的只有 38 个（4.4%）。
  说明病根不是「账号进了标题」，而是**一段 L1 文本同时承担「个案事实」与「可复用模式」
  两个互相冲突的职责**——要具体到单就必然碎。
  解法不是调阈值，是拆字段：root_cause 记个案事实（允许带单号账号），
  root_pattern 记受控模式（禁用户级信息），**簇键只来自 root_pattern 的三要素**。

设计原则（对齐单一真相源铁律）：
  1. 机制 / 对象 / 环节枚举只在此声明一次；prompt、校验、聚合、前端下拉全部由本文件派生；
  2. 落库值即中文名（零转译，同 fault_stage / fault_type）；
  3. **新增一枚枚举 = 本文件加一行**（DB 列为 String，无需迁移）；
  4. 严禁在 prompt、前端、脚本里另写第二份清单。

三维分工（为什么只有这三维当键，见 docs/客诉根因聚类方法论.md §3）：
  stage      订单环节 —— 断点在哪一环（复用 FAULT_STAGES，不另建第二份）
  mechanism  失败机制 —— 怎么断的（收敛轴：一机制 ≈ 一个可一次性修复的缺陷单元）
  biz_object 业务对象 —— 断在谁身上（同机制同环节，对象不同才允许拆簇）
产品线 / 责任系统 / 触发条件**不进键**：系统是「断点归因」不是「问题身份」
（实测同一问题被拆到 CRM/电视平台/订单中心 3 个系统桶、合计 28 单），只做属性。
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from constants.complaint_rootcause import FAULT_STAGES, GENERIC_TERMS

# ── 订单环节（复用 L1 枚举，禁第二份）────────────────────────────
STAGES: Tuple[str, ...] = FAULT_STAGES


# ── 失败机制（21 项 + 兜底）───────────────────────────────────────
# 分组只用于 prompt 展示与前端分栏，判定时一律平铺查全表。
MECHANISM_GROUPS: Dict[str, Tuple[str, ...]] = {
    "数据流断裂": (
        "未下发",       # 上游没把对象发往下游（无单、无报文、无指令）
        "未回写",       # 下游没把结果回传上游（状态不推进）
        "未同步",       # 两侧都有数据但值不一致（复制缺失/延迟）
        "未级联",       # 主对象变更未联动子对象（销户/停机/复机/退订）
        "未归档",       # 流程已结束但单据未终结，资态滞留阻塞后续
        "未生成",       # 应创建的对象未创建（无单可办）
        "流转失败",     # 已发出但调度/路由失败，卡在某节点
    ),
    "校验与配置": (
        "校验拦截",     # 规则/校验错误阻断合法业务
        "字段缺失",     # 必填未填、逐行映射遗漏、报文缺属性
        "配置错误",     # 产品/资费/参数/权限配置错或缺失
        "权限不足",     # 菜单/功能/数据范围权限不足
        "编码不规范",   # 超长、非法字符、字符集不兼容
    ),
    "能力与规则": (
        "功能入口缺失",  # 无撤单/无批量/无查询/无编辑入口
        "状态展示不一致",  # 界面与后端、新旧版口径不一致
        "规则不合理",    # 业务规则或流程设计阻断正常诉求
        "重复开通",      # 重复开通/重复出账/重复派单
        "计费错误",      # 错扣/漏扣/折算错/归属错
        "性能容量",      # 超时、并发、批量瓶颈
        "脏数据残留",    # 存量错误数据妨碍新业务
    ),
    "非缺陷与兜底": (
        "使用咨询",      # 操作不熟/认知偏差，系统与流程正常（不进根因簇）
        "其他",          # 枚举未覆盖（记 gap，等月度重构补枚举）
    ),
}

MECHANISMS: Tuple[str, ...] = tuple(
    m for group in MECHANISM_GROUPS.values() for m in group)

# 这些机制不生成根因簇：使用咨询 → is_defect=0 单列；其他 → 落兜底簇
MECHANISM_CONSULT = "使用咨询"
MECHANISM_FALLBACK = "其他"
# 信息不足不建簇（rc_status=insufficient 直接不进聚类），故不进 MECHANISMS
MECHANISM_INSUFFICIENT = "信息不足"


# ── 业务对象（6 域 34 项 + 兜底）──────────────────────────────────
OBJECT_GROUPS: Dict[str, Tuple[str, ...]] = {
    "订单域": ("订单", "订单状态", "在途单", "购物车", "批量导入任务", "稽核单", "待办"),
    "施工域": ("施工单", "派单指令", "竣工结果", "装维回单", "施工队列", "上门记录"),
    "产品域": ("产品实例", "产品配置", "资费项", "营销案", "套餐关系", "资源端口"),
    "客户域": ("客户资料", "集团编码", "成员关系", "协议", "协议模板"),
    "账号域": ("宽带账号", "电视账号", "IPTV账号", "账号状态", "权限"),
    "账务域": ("账单", "出账记录", "缴费流水", "发票", "欠费状态"),
}

OBJECTS: Tuple[str, ...] = tuple(
    o for group in OBJECT_GROUPS.values() for o in group) + (MECHANISM_FALLBACK,)

OBJECT_FALLBACK = MECHANISM_FALLBACK   # 「其他」，同一兜底值

# 上下位对象（例外通道 B）：同机制下这些对象可合并到上位对象，不拆簇。
# key = 下位，value = 上位。只列真实存在父子关系的，禁止为凑数硬加。
OBJECT_PARENT: Dict[str, str] = {
    "订单状态": "订单",
    "账号状态": "宽带账号",
    "竣工结果": "施工单",
    "装维回单": "施工单",
    "派单指令": "施工单",
    "施工队列": "施工单",
    "出账记录": "账单",
    "欠费状态": "账号状态",
    "缴费流水": "账单",
    "产品配置": "产品实例",
    "资费项": "产品实例",
    "套餐关系": "产品实例",
    "协议模板": "协议",
}

# 相邻环节（例外通道 A）：同机制同对象、环节属同一业务流相邻对时，归到断点环节。
# 单条环节判定不稳是已知噪声源，故允许合并，但必须落在白名单内。
ADJACENT_STAGE_PAIRS: Tuple[Tuple[str, str], ...] = (
    ("前台受理", "协议签约"),
    ("协议签约", "订单开通"),
    ("订单开通", "装维交付"),
    ("装维交付", "业务激活"),
    ("业务激活", "数据同步"),
    ("数据同步", "计费出账"),
    ("计费出账", "账务结算"),
    ("产品配置", "订单开通"),
)


# ── 数量预算（防止再次膨胀；超限先报警，不硬压质量）──────────────────
TARGET_CLUSTER_MAX = 100      # 本期目标：有效簇 ≤100
BUCKET_CLUSTER_MAX = 2        # 同一（环节 × 机制）下最多允许的簇数，超了进兜底
SINGLE_CLUSTER_RATE_MAX = 0.15   # 单簇率目标（当前 90.4%）
MISMATCH_RATE_MAX = 0.10      # 未匹配率（落兜底桶的单量占比）目标


# ── 用户级信息门禁（root_pattern 的反向要求：**必须不含**）────────────
# 与 root_cause 的 G3「必须带具体标识」正好相反——这是双字段解耦的关键。
USER_LEVEL_PATTERNS: Tuple[Tuple[str, str], ...] = (
    (r"\d{6,}", "连续 6 位以上数字（账号/单号/协议号）"),
    (r"1[3-9]\d{9}", "手机号"),
    (r"\d{17}[\dXx]", "身份证号"),
    (r"[\u4e00-\u9fa5]{2,}(市|区|县|镇|街道)[\u4e00-\u9fa5]{1,6}(路|街|巷|号|栋|楼|室)", "地名门牌"),
    (r"\b[A-Z]{2,}\d{4,}\b", "带前缀的编号串"),
)

# 泛词（沿用 L1 既有黑名单，不另建第二份）

PATTERN_MAX_CHARS = 60        # root_pattern 长度上限（10~60 字）


def stage_options() -> List[str]:
    return list(STAGES)


def mechanism_options() -> List[str]:
    return list(MECHANISMS)


def object_options() -> List[str]:
    return list(OBJECTS)


def mechanism_of_group() -> Dict[str, str]:
    """机制 → 所属分组（prompt 展示 / 前端分栏用）。"""
    return {m: g for g, ms in MECHANISM_GROUPS.items() for m in ms}


def normalize_mechanism(value: str) -> str:
    """把 LLM 输出对齐到机制枚举（精确 → 包含 → 空，绝不编造）。"""
    return _normalize(value, MECHANISMS)


def normalize_object(value: str) -> str:
    return _normalize(value, OBJECTS)


def _normalize(value: str, options: Tuple[str, ...]) -> str:
    v = (value or "").strip().replace(" ", "")
    if not v:
        return ""
    if v in options:
        return v
    # 包含匹配按「选项长度降序」，避免「订单」吃掉「订单状态」
    for o in sorted(options, key=len, reverse=True):
        if o and (o in v or v in o):
            return o
    return ""


def upper_object(obj: str) -> str:
    """沿 OBJECT_PARENT 链上溯到上位对象（例外通道 B，最多 3 跳防环）。"""
    cur = (obj or "").strip()
    for _ in range(3):
        nxt = OBJECT_PARENT.get(cur)
        if not nxt:
            break
        cur = nxt
    return cur


def stages_adjacent(a: str, b: str) -> bool:
    a, b = (a or "").strip(), (b or "").strip()
    if not a or not b or a == b:
        return a == b
    return (a, b) in ADJACENT_STAGE_PAIRS or (b, a) in ADJACENT_STAGE_PAIRS


# ── 模式串与簇键 ────────────────────────────────────────────────
KEY_SEP = "|"


def build_pattern(mechanism: str, obj: str, trigger: str = "") -> str:
    """拼 root_pattern：`{对象}-{机制}` 或 `{对象}-{机制}（{触发条件}）`。

    只做拼装，不做校验（校验见 pattern_violations）。
    """
    m = (mechanism or "").strip()
    o = (obj or "").strip()
    if not m or not o:
        return ""
    base = f"{o}-{m}"
    t = (trigger or "").strip()
    return f"{base}（{t}）"[:PATTERN_MAX_CHARS] if t else base[:PATTERN_MAX_CHARS]


def pattern_key(stage: str, mechanism: str, obj: str) -> str:
    """L2 簇唯一键：环节 + 机制 + 上位对象（三元组）。

    上位对象上溯在这里统一做——入库、匹配、合并三处必须走同一个函数，
    否则「施工单」与「派单指令」会各建一簇（历史上正是这么碎的）。
    """
    return KEY_SEP.join(((stage or "").strip(),
                         (mechanism or "").strip(),
                         upper_object(obj)))


def split_pattern_key(key: str) -> Tuple[str, str, str]:
    parts = (key or "").split(KEY_SEP)
    parts += [""] * (3 - len(parts))
    return parts[0], parts[1], parts[2]


def pattern_violations(text: str) -> List[str]:
    """root_pattern / 簇标题的用户级信息门禁，返回命中原因（空 = 合格）。"""
    s = (text or "").strip()
    out: List[str] = []
    if not s:
        return ["模式为空"]
    for pat, label in USER_LEVEL_PATTERNS:
        if re.search(pat, s):
            out.append(f"含用户级信息：{label}")
    if len(s) > PATTERN_MAX_CHARS:
        out.append(f"模式过长（{len(s)}字 > {PATTERN_MAX_CHARS}）")
    # 泛词校验前先剔除机制名本身——「流转失败」「校验拦截」是受控枚举，不是空话
    generic_src = s
    for m in MECHANISMS:
        generic_src = generic_src.replace(m, "")
    hits = [t for t in GENERIC_TERMS if t and t in generic_src]
    if hits:
        out.append("含泛词：" + "、".join(hits[:3]))
    return out


def is_clusterable(mechanism: str) -> bool:
    """该机制是否应生成根因簇（使用咨询单独统计，其他落兜底）。"""
    m = (mechanism or "").strip()
    return bool(m) and m not in (MECHANISM_CONSULT, MECHANISM_INSUFFICIENT)


# ── 判定决策表（prompt 与文档共用，禁第二份文案）────────────────────
MECHANISM_RULES: Tuple[Tuple[str, str], ...] = (
    ("下游说「没有这个单 / 没收到」", "未下发"),
    ("上游说「不知道结果 / 状态没变」", "未回写"),
    ("两边都有记录但值不同", "未同步"),
    ("主业务已变更（销户/停机/退订/复机），子对象没跟着变", "未级联"),
    ("流程已结束单据却没终结，卡住后续业务", "未归档"),
    ("该有的单/记录根本没生成", "未生成"),
    ("单子已发出但卡在某个节点不动", "流转失败"),
    ("提交时被规则挡住，业务本身合法", "校验拦截"),
    ("报文/表单缺字段或映射错位", "字段缺失"),
    ("产品/资费/参数配错或未配置", "配置错误"),
    ("界面上找不到入口/按钮/菜单", "功能入口缺失"),
    ("界面显示与后台实际不一致", "状态展示不一致"),
    ("按规则解释得通但规则本身不合理", "规则不合理"),
    ("同一对象被重复开通/重复出账/重复派单", "重复开通"),
    ("金额错扣/漏扣/折算错/归属错", "计费错误"),
    ("超时、并发、批量处理不动", "性能容量"),
    ("存量错误数据妨碍新业务", "脏数据残留"),
    ("处理意见只有「已指导/已告知/已解释」，无技术动作", "使用咨询"),
)


def mechanism_rules_block() -> str:
    """机制判定决策表（prompt 用；保证文档与 prompt 同一份文案）。"""
    return "\n".join(f"  · {a} → {b}" for a, b in MECHANISM_RULES)


def enum_block() -> str:
    """L1 prompt 用的模式枚举块（机制 + 对象，按域分组便于模型选）。"""
    mech = "\n".join(f"  [{g}] {'、'.join(ms)}" for g, ms in MECHANISM_GROUPS.items())
    obj = "\n".join(f"  [{g}] {'、'.join(os)}" for g, os in OBJECT_GROUPS.items())
    return (
        "【失败机制 mechanism（只能从每个分组里挑一个具体机制）】\n" + mech + "\n"
        "  ※ 方括号里的是**分组名，不是可选值**，不得填「数据流断裂」「校验与配置」"
        "「能力与规则」「非缺陷与兜底」这类分组名。\n"
        "【业务对象 biz_object（只能从中选一个，禁自由造词）】\n" + obj
    )


def meta() -> Dict[str, object]:
    """前端 /meta 导出（与 complaint_rootcause.enum_meta 合并返回）。"""
    return {
        "mechanisms": [
            {"value": m, "group": g} for g, ms in MECHANISM_GROUPS.items() for m in ms],
        "objects": [
            {"value": o, "group": g} for g, os in OBJECT_GROUPS.items() for o in os],
        "pattern_key_sep": KEY_SEP,
        "target_cluster_max": TARGET_CLUSTER_MAX,
        "bucket_cluster_max": BUCKET_CLUSTER_MAX,
    }
