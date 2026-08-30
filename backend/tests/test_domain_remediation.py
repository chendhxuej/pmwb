"""领域树整治规划（T2 / P0）测试：只读 dry-run，验证分组/路径归并映射正确、零副作用。

覆盖 §3.7 关键规则：
- cj-xs 场景化销售 误标商客业务 -> 公共能力
- 业务域（一网通宽带）保持、无需修正
- 系统平台域 vault_path 误写虚构中间层 -> 修正为权威路径
- 其他政企业务（enabled=0）弱化处理、不进主线
"""
from db.models import PmwbBusinessDomain
from services import domain_remediation


def _add(db, code, name, group, vault_path=None, enabled=True):
    d = PmwbBusinessDomain(
        domain_code=code,
        domain_name=name,
        domain_group=group,
        vault_path=vault_path or f"01-业务知识/{group}/{name}",
        enabled=enabled,
    )
    db.add(d)
    db.commit()
    return d


def test_target_vault_path():
    assert domain_remediation.target_vault_path("商客业务", "一网通宽带") == "01-业务知识/商客业务/一网通宽带"
    assert domain_remediation.target_vault_path("系统平台", "电子协议") == "01-业务知识/系统平台/电子协议"


def test_keep_business_unchanged(db):
    _add(db, "ywt-broadband", "一网通宽带", "商客业务")
    plan = domain_remediation.compute_remediation_plan(db)
    assert all(f["domain_code"] != "ywt-broadband" for f in plan["field_fixes"])


def test_cjxs_group_override(db):
    # cj-xs 场景化销售：domain_group 误标商客业务，vault 已在公共能力
    _add(db, "cj-xs", "场景化销售", "商客业务", "01-业务知识/公共能力/场景化销售")
    plan = domain_remediation.compute_remediation_plan(db)
    fx = next((f for f in plan["field_fixes"] if f["domain_code"] == "cj-xs"), None)
    assert fx is not None
    assert fx["new_group"] == "公共能力"
    assert fx["new_vault_path"] == "01-业务知识/公共能力/场景化销售"


def test_system_platform_vault_path_fix(db):
    # e-contract vault_path 误写虚构中间层「政企业务知识库/业务平台/电子协议平台」
    _add(db, "e-contract", "电子协议", "系统平台", "01-业务知识/政企业务知识库/业务平台/电子协议平台")
    plan = domain_remediation.compute_remediation_plan(db)
    fx = next((f for f in plan["field_fixes"] if f["domain_code"] == "e-contract"), None)
    assert fx is not None
    assert fx["new_vault_path"] == "01-业务知识/系统平台/电子协议"
    # 同时应生成 vault 目录移动清单（旧虚构中间层 -> 新权威路径）
    mv = next((m for m in plan["file_moves"] if m["domain_code"] == "e-contract"), None)
    assert mv is not None
    assert mv["old_dir"] == "01-业务知识/政企业务知识库/业务平台/电子协议平台"
    assert mv["new_dir"] == "01-业务知识/系统平台/电子协议"


def test_disabled_other_government_skipped(db):
    _add(db, "zx-special", "专线", "政企业务", "01-业务知识/政企业务知识库/专线", enabled=False)
    plan = domain_remediation.compute_remediation_plan(db)
    assert all(f["domain_code"] != "zx-special" for f in plan["field_fixes"])
    assert any(s["domain_code"] == "zx-special" for s in plan["skipped"])


def test_plan_is_readonly_no_side_effect(db):
    """dry-run 不得修改 DB（零副作用）。"""
    d = _add(db, "ywt-broadband", "一网通宽带", "商客业务", "01-业务知识/商客业务/一网通宽带")
    domain_remediation.compute_remediation_plan(db)
    db.refresh(d)
    assert d.domain_group == "商客业务"  # 未被改动
    assert d.vault_path == "01-业务知识/商客业务/一网通宽带"
