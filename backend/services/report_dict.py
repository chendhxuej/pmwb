"""AI总结报告 —— 内部枚举值中文转译字典。

采集器把业务表的原始枚举（状态/分类/优先级/影响等级）原样喂给报告与 LLM，
导致报告里充斥 pending/resolved/prod/P0 等内部编码。本模块集中维护「编码 → 中文标签」
映射，供 report_collector（聚合键转译 + 明细字段转译）与 report_prompt（注入 glossary）复用。
"""
from __future__ import annotations

from typing import Dict

# ---- 需求与交付 ----
REQUIREMENT_STATUS: Dict[str, str] = {
    "proposed": "已提出",
    "accepted": "已接纳",
    "dev": "开发中",
    "closed": "已上线",
    "paused": "已暂停",
}

# 需求个人优先级：含自由文本（集团需求/紧急需求），需兜底
REQUIREMENT_PRIORITY: Dict[str, str] = {
    "P0": "最高(P0)",
    "P1": "高(P1)",
    "P2": "中(P2)",
    "P3": "低(P3)",
    "集团需求": "集团级需求",
    "紧急需求": "紧急需求",
}

# ---- 开发工单 ----
DEV_TICKET_STATUS: Dict[str, str] = {
    "created": "已创建",
    "design_reviewed": "设计已评审",
    "dev_completed": "开发完成",
    "test_completed": "测试完成",
    "live": "已上线",
    "archived": "已归档",
}

# ---- 运营工单 ----
OP_ISSUE_CATEGORY: Dict[str, str] = {
    "bug": "BUG管理",
    "data": "数据异常管理",
    "prod": "主动运营分析",
    "task": "临时交办任务",
    "complaint": "热点投诉",
}

OP_ISSUE_TYPE: Dict[str, str] = {
    "bug": "BUG",
    "data_abnormal": "数据异常",
    "topic_analysis": "专题分析",
    "spot_event": "投点事件",
    "temp_task": "临时任务",
    "other": "其他",
}

OP_ISSUE_STATUS: Dict[str, str] = {
    "pending": "待处理",
    "processing": "处理中",
    "verify": "待验证",
    "resolved": "已解决",
    "closed": "已关闭",
    "suspended": "已挂起",
}

# ---- 影响等级（运营/开发/待办通用 P0-P3）----
IMPACT_LEVEL: Dict[str, str] = {
    "P0": "致命(P0)",
    "P1": "严重(P1)",
    "P2": "一般(P2)",
    "P3": "轻微(P3)",
}

# ---- 个人待办 ----
TODO_STATUS: Dict[str, str] = {
    "todo": "待办",
    "in_progress": "进行中",
    "done": "已完成",
    "cancelled": "已取消",
}

TODO_CATEGORY: Dict[str, str] = {
    "requirement": "需求",
    "ticket": "开发工单",
    "operation": "运营",
    "meeting": "会议",
    "study": "学习",
    "other": "其他",
}

# 会议行动项状态（自由文本，约定值）
MEETING_ACTION_STATUS: Dict[str, str] = {
    "pending": "待办",
    "in_progress": "进行中",
    "done": "已完成",
    "closed": "已关闭",
}

# 所有字典按模块归类，便于 prompt 注入 glossary
GLOSSARY: Dict[str, Dict[str, str]] = {
    "需求状态": REQUIREMENT_STATUS,
    "需求优先级": REQUIREMENT_PRIORITY,
    "开发工单状态": DEV_TICKET_STATUS,
    "运营工单大类": OP_ISSUE_CATEGORY,
    "运营工单子类": OP_ISSUE_TYPE,
    "运营工单状态": OP_ISSUE_STATUS,
    "影响等级": IMPACT_LEVEL,
    "待办状态": TODO_STATUS,
    "待办分类": TODO_CATEGORY,
    "会议行动项状态": MEETING_ACTION_STATUS,
}


def tr(table: Dict[str, str], code, default=None) -> str:
    """单值转译：命中映射返回中文标签，未命中返回 default（默认回退原值）。"""
    if code is None:
        return default if default is not None else ""
    s = str(code)
    return table.get(s, default if default is not None else s)


def tr_multi(table: Dict[str, str], codes) -> str:
    """把一组编码（列表/元组/逗号分隔串）转成中文标签串，逗号连接。

    用于 priority 等可能含多值或自由文本的场景。自由文本（如「集团需求」）命中字典即转译，
    未命中（如「紧急上线」）原样保留。
    """
    if codes is None:
        return ""
    if isinstance(codes, str):
        parts = [p.strip() for p in codes.split(",") if p.strip()]
    else:
        parts = [str(c).strip() for c in codes if c is not None]
    return "、".join(tr(table, p) for p in parts)


def tr_keys(table: Dict[str, str], counted: Dict[str, int]) -> Dict[str, int]:
    """把聚合字典的键（英文码）整体转成中文键，值不变。"""
    return {tr(table, k): v for k, v in (counted or {}).items()}
