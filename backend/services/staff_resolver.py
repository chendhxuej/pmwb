"""人员解析器：统一将姓名字符串解析为 staff_id。

所有业务服务通过此入口解析人员，避免重复代码。
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from utils.master_service import master_service_client

logger = logging.getLogger(__name__)

# 本地 LRU 缓存（进程级，简单实现）
_cache: Dict[str, Optional[int]] = {}


def resolve_staff_id(name: str) -> Optional[int]:
    """按姓名解析 staff_id。

    优先查本地缓存，未命中则调 master 服务。
    同名多人时返回第一个 enabled（已按 sort 排序）。
    """
    if not name or not name.strip():
        return None

    name = name.strip()

    if name in _cache:
        return _cache[name]

    staff_id = master_service_client.resolve_staff_id(name)
    _cache[name] = staff_id
    return staff_id


def resolve_staff_ids(names: List[str]) -> List[int]:
    """批量解析姓名列表为 staff_id 列表。跳过空名和未匹配。"""
    ids = []
    for name in names:
        sid = resolve_staff_id(name)
        if sid:
            ids.append(sid)
    return ids


def resolve_staff_ids_json(names: List[str]) -> List[int]:
    """解析为 JSON 数组（用于多值字段如 handler_staff_ids）。"""
    return resolve_staff_ids(names)


def invalidate_cache():
    """清空本地缓存（人员数据变更后调用）。"""
    _cache.clear()
