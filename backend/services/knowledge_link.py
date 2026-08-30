"""知识关联服务（kc-4 T7 合并收敛）。

原 services/knowledge_link.py 的「## 关联对象」章节同步逻辑已统一收敛到
services.knowledge_link_service.py（单一实现：维护 DB 关联 + 主笔记 frontmatter
related_* 数组 + 正文「## 7. 关联过程性内容索引」章节）。

本文件仅保留向后兼容的 re-export 薄壳，避免任何既有导入方因路径变化而失效。
请勿在本文件新增任何业务逻辑——所有关联能力以 knowledge_link_service 为准。
"""
from services.knowledge_link_service import (  # noqa: F401
    SOURCE_LABELS,
    SOURCE_LABELS_LEGACY,
    _get_or_create_item_by_path,
    _serialize,
    _sync_backlinks,
    link_note,
    link_to_item,
    link_to_path,
    list_by_item,
    list_links,
    unlink,
    unlink_by_link_id,
)
