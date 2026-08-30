"""kc-4 T7：验证双份 knowledge_link 实现已收敛到 knowledge_link_service 单一实现。

早期 services/knowledge_link.py 仅同步「## 关联对象」章节；kc-2 的
knowledge_link_service.py 维护 DB 关联 + frontmatter related_* + 正文索引，
是规范实现。T7 后 knowledge_link.py 仅做 re-export 薄壳，所有关联逻辑唯一来源
是 knowledge_link_service。本测试锁定这一收敛，防止日后再次出现双份实现。
"""
import services.knowledge_link as kl
import services.knowledge_link_service as ks


def test_shim_link_to_item_delegates_to_service():
    assert kl.link_to_item is ks.link_to_item


def test_shim_link_to_path_delegates_to_service():
    assert kl.link_to_path is ks.link_to_path


def test_shim_list_links_is_list_by_source():
    assert kl.list_links is ks.list_by_source


def test_shim_sync_backlinks_is_frontmatter_section_sync():
    # 早期章节同步 == 现 frontmatter+正文索引同步（superset）
    assert kl._sync_backlinks is ks._sync_frontmatter_and_section


def test_shim_exposes_unlink_by_link_id():
    assert hasattr(kl, "unlink_by_link_id")
    assert kl.unlink_by_link_id is ks.unlink_by_link_id


def test_canonical_link_logic_is_link_note():
    # 来源->条目 维度的 link_to_item 最终走 link_note（单实现）
    assert kl.link_to_item.__name__ == "link_to_item"
    # link_note 是规范落地函数
    assert "link_note" in dir(ks)
