"""客诉问题分类引擎 —— 规则全部来自 pmwb_complaint_category 字典表。

设计原则（对应「单一真相源」铁律）：
  - 关键词正则只存一处（字典表 keywords 列），本模块不含任何硬编码分类词；
  - 匹配顺序由字典 sort_order 决定：先二级具体场景，后一级笼统性质兜底；
  - 分类结果落 category_l1 / category_l2 中文名，零转译。

改口径 = 改字典表，不需要改代码、不需要重新部署。
"""

from __future__ import annotations

import re
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

UNCLASSIFIED = "未分类"


class Rule(NamedTuple):
    level: int
    parent: Optional[str]
    name: str
    pattern: "re.Pattern[str]"
    sort_order: int


class Dictionary:
    """分类字典的内存快照（进程内缓存，避免逐单查库）。"""

    def __init__(self, rules: Sequence[Rule]):
        self.rules: List[Rule] = list(rules)
        self._l2 = [r for r in self.rules if r.level == 2]
        self._l1 = [r for r in self.rules if r.level == 1]

    def classify(self, content: str, solution: str = "") -> Tuple[str, str, str]:
        """返回 (一级, 二级, 命中依据)。

        先按 sort_order 逐条匹配二级场景；全部未命中再用一级兜底；
        仍未命中返回 (未分类, "", 空)。
        """
        haystack = f"{content or ''}\n{solution or ''}"
        for rule in self._l2:
            if rule.pattern.search(haystack):
                return rule.parent or UNCLASSIFIED, rule.name, rule.name
        for rule in self._l1:
            if rule.pattern.search(haystack):
                return rule.name, "", rule.name
        return UNCLASSIFIED, "", ""

    def l1_names(self) -> List[str]:
        return [r.name for r in self._l1]

    def l2_map(self) -> Dict[str, str]:
        """二级名 → 一级名。"""
        return {r.name: (r.parent or UNCLASSIFIED) for r in self._l2}


_CACHE: Dict[str, Dictionary] = {}


def load_dictionary(db: Session, use_cache: bool = True) -> Dictionary:
    """从字典表加载启用的分类规则（按 sort_order 升序）。"""
    if use_cache and "dict" in _CACHE:
        return _CACHE["dict"]

    rows = db.execute(text(
        "SELECT level, parent_name, name, keywords, sort_order "
        "FROM pmwb_complaint_category WHERE enabled = 1 ORDER BY sort_order ASC"
    )).fetchall()

    rules: List[Rule] = []
    for level, parent, name, keywords, sort_order in rows:
        if not keywords:
            continue
        try:
            pattern = re.compile(keywords)
        except re.error:
            continue
        rules.append(Rule(int(level), parent, name, pattern, int(sort_order)))

    dic = Dictionary(rules)
    _CACHE["dict"] = dic
    return dic


def clear_cache() -> None:
    _CACHE.clear()
