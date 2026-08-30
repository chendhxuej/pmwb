"""领域树整治规划（T2 / P0 硬前置）：只读 dry-run，零副作用。

基于方案 §3.7「分目录管理铁律 + 归并映射」，对业务领域（DB）做一致性核查，
生成可执行的修正规划清单，**不落盘、不移动文件**，先给老大过目确认后再由 T9 备份执行。

产出：
- field_fixes：DB 的 domain_group / vault_path 需修正项（与权威源不一致）
- file_moves ：vault 目录需移动项（old_dir -> new_dir），T9 实际执行
- skipped     ：其他政企业务（enabled=0）弱化处理，不进知识中心主线

规则要点（详见方案 §3.7）：
- 四类分组：商客业务 / 系统平台 / 公共能力 / 通用
- 分目录管理铁律：业务笔记/系统平台笔记/公共能力/通用 分目录，互不串门
- 商客业务目录下不得存放系统平台主笔记（T9 上提整合）
- 其他政企业务（专线/短信/卫星/国铁/国际）enabled=0，弱化处理
- 错配修正：cj-xs 场景化销售 误标商客业务 -> 公共能力
"""
from db.models import PmwbBusinessDomain
from services.obsidian_paths import BUSINESS_KNOWLEDGE_DIR

# 代码级分组错配修正（DB domain_group 与真实业务归属不符）
GROUP_OVERRIDE = {
    "cj-xs": "公共能力",  # 场景化销售：vault 已在公共能力，domain_group 误标商客业务
}


def target_vault_path(group: str, name: str) -> str:
    """领域在 vault 下的权威相对路径：01-业务知识/{group}/{name}。"""
    return f"{BUSINESS_KNOWLEDGE_DIR}/{group}/{name}"


def normalize_group(domain) -> str:
    """返回领域应归属的正确分组（应用代码级错配修正）。"""
    if domain.domain_code in GROUP_OVERRIDE:
        return GROUP_OVERRIDE[domain.domain_code]
    return domain.domain_group


def compute_remediation_plan(db) -> dict:
    """扫描全部业务领域，返回修正规划（只读，不落盘）。"""
    field_fixes = []
    skipped = []
    domains = db.query(PmwbBusinessDomain).all()
    for d in domains:
        if not d.enabled:
            # 其他政企业务弱化处理，不进主线
            skipped.append({
                "domain_code": d.domain_code,
                "domain_name": d.domain_name,
                "reason": "enabled=0 其他政企业务，弱化处理不进知识中心主线",
            })
            continue
        new_group = normalize_group(d)
        new_vault = target_vault_path(new_group, d.domain_name)
        group_changed = new_group != d.domain_group
        path_changed = (d.vault_path or "") != new_vault
        if group_changed or path_changed:
            reason = []
            if group_changed:
                reason.append(f"domain_group 误标 {d.domain_group} -> {new_group}")
            if path_changed:
                reason.append("vault_path 与权威源不一致")
            field_fixes.append({
                "domain_code": d.domain_code,
                "domain_name": d.domain_name,
                "old_group": d.domain_group,
                "new_group": new_group,
                "old_vault_path": d.vault_path,
                "new_vault_path": new_vault,
                "reason": "；".join(reason),
            })
    # vault 目录移动清单：由 field_fixes 中 vault_path 变更推导（old_dir -> new_dir）
    file_moves = []
    for fx in field_fixes:
        if fx["old_vault_path"] and fx["old_vault_path"] != fx["new_vault_path"]:
            file_moves.append({
                "domain_code": fx["domain_code"],
                "old_dir": fx["old_vault_path"],
                "new_dir": fx["new_vault_path"],
                "group_lifted": fx["old_group"] == "商客业务" and fx["new_group"] == "系统平台",
            })
    return {"field_fixes": field_fixes, "file_moves": file_moves, "skipped": skipped}
