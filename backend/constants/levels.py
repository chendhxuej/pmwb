"""级别（优先级/影响等级）口径 —— 全站唯一真相源。

背景（任务中心「高级别工单」子模块，2026-10-15）：
  各来源表的级别字段**列名与取值形态不统一**，但语义同源：
    - 运营工单 / 一线调研：`impact_level`（Enum P0-P3）
    - 开发工单 / 个人待办 / 重点工作：`priority`（Enum P0-P3）
    - 主动优化：`priority`（String(16)）
    - 需求：`priority`（String(64)，**自由文本**，含「集团需求 / 紧急需求」）
    - 会议行动项 / 重点工作子项：**无级别字段**
  历史实现（services/report_collector.py）用中文字符串硬编码
  `imp in ("致命(P0)", "严重(P1)")` 判高级别 —— 与英文码域是「同一口径两种表示」。

本模块把「规范码 / 中文标签 / 自由文本」三态统一到一处，供判定与展示复用，
严禁在别处再写第二份级别映射。
"""

from __future__ import annotations

from typing import Any, Optional, Tuple

from services.report_dict import IMPACT_LEVEL

# 规范码（英文，落库与内部判定使用）
KNOWN_CODES: Tuple[str, ...] = tuple(IMPACT_LEVEL.keys())  # ("P0", "P1", "P2", "P3")

# 高级别码：命中即视为高级别（R1）
HIGH_LEVEL_CODES: Tuple[str, ...] = ("P0", "P1")

# 高级别码对应的中文标签（供 report_collector 等以标签域工作的旧代码复用）
HIGH_LEVEL_LABELS: Tuple[str, ...] = tuple(IMPACT_LEVEL[c] for c in HIGH_LEVEL_CODES)  # ("致命(P0)", "严重(P1)")

# 需求 priority 是自由文本，这两个词等价于高级别（不映射为 P 码，单独判定）
HIGH_LEVEL_FREE_TEXT: Tuple[str, ...] = ("集团需求", "紧急需求")

# 中文标签 → 规范码（反向映射）
_CODE_BY_LABEL = {v: k for k, v in IMPACT_LEVEL.items()}

# 自由文本 → 展示用短标签
_FREE_TEXT_LABEL = {
    "集团需求": "集团需求",
    "紧急需求": "紧急需求",
}


def _raw_to_str(raw: Any) -> str:
    """把任意形态的级别原始值规整成字符串（兼容 Enum / None / 前后空格）。"""
    if raw is None:
        return ""
    val = getattr(raw, "value", raw)  # Python Enum → 其值
    return str(val).strip()


def normalize_priority(raw: Any) -> Optional[str]:
    """级别原始值 → 规范码（P0/P1/P2/P3）。

    接受：`"P0"` / `"p0"` / `"致命(P0)"` / Enum 成员。
    无法识别（含「集团需求」「紧急需求」等自由文本）→ 返回 None，**宁漏勿错**。
    """
    s = _raw_to_str(raw)
    if not s:
        return None
    upper = s.upper()
    if upper in IMPACT_LEVEL:
        return upper
    if s in _CODE_BY_LABEL:
        return _CODE_BY_LABEL[s]
    return None


def is_free_text_high(raw: Any) -> bool:
    """需求 priority 自由文本是否属于高级别词（集团需求 / 紧急需求）。"""
    return _raw_to_str(raw) in HIGH_LEVEL_FREE_TEXT


def is_high_level(raw: Any) -> bool:
    """级别原始值是否为高级别（规范码域 + 自由文本域，两种表示都认）。

    这是本模块对外的主判定入口；`is_high_level_code` / `is_high_level_label`
    均为其语义别名，保留以兼容按「码域」「标签域」思维的调用方。
    """
    code = normalize_priority(raw)
    if code is not None:
        return code in HIGH_LEVEL_CODES
    return is_free_text_high(raw)


def is_high_level_code(raw: Any) -> bool:
    """按规范码域判定（自由文本不认）。"""
    return normalize_priority(raw) in HIGH_LEVEL_CODES


def is_high_level_label(raw: Any) -> bool:
    """兼容旧调用（report_collector 以中文标签工作）：标签/码/自由文本三态统一判定。"""
    return is_high_level(raw)


def priority_label(raw: Any) -> str:
    """级别原始值 → 中文展示标签；无法识别时原样回退（空则「—」）。"""
    code = normalize_priority(raw)
    if code is not None:
        return IMPACT_LEVEL.get(code, code)
    s = _raw_to_str(raw)
    if s in _FREE_TEXT_LABEL:
        return _FREE_TEXT_LABEL[s]
    return s or "—"


def level_rank(raw: Any) -> int:
    """级别排序权重（P0 最小=最高优先级）；无法识别排在最后。"""
    code = normalize_priority(raw)
    if code is not None and code in KNOWN_CODES:
        return KNOWN_CODES.index(code)
    if is_free_text_high(raw):
        return 0  # 与 P0 同档处理，保证同组内排在最前
    return len(KNOWN_CODES)


__all__ = [
    "KNOWN_CODES",
    "HIGH_LEVEL_CODES",
    "HIGH_LEVEL_LABELS",
    "HIGH_LEVEL_FREE_TEXT",
    "normalize_priority",
    "is_free_text_high",
    "is_high_level",
    "is_high_level_code",
    "is_high_level_label",
    "priority_label",
    "level_rank",
]
