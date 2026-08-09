"""业务知识路径权威源（kc-3 / P0）。

集中计算各业务领域在 Obsidian vault 下的笔记目录，避免散落硬编码导致的
口径不一致（此前运营/会议/开发交付各自写死 11-业务运营/、05-会议纪要/、
14-知识沉淀/开发交付/ 等非领域树路径，与"业务知识主笔记"所在的
`01-业务知识/{group}/{name}/` 树割裂）。

统一约定（领域树）：
    01-业务知识/{domain_group}/{domain_name}/
        ├─ 03-业务规则/      （场景规则子笔记，sediment_operation_rules）
        ├─ 05-交付物/        （操作手册归档，archive_requirement_manual）
        ├─ 运营/             （运营工单沉淀，sediment_operation_issue）
        ├─ 会议/             （会议纪要沉淀，sediment_meeting）
        └─ 开发交付/          （开发工单沉淀，sediment_dev_ticket）
"""
from db.models import PmwbBusinessDomain
from core.exceptions import NotFoundException

# 领域树根目录名
BUSINESS_KNOWLEDGE_DIR = "01-业务知识"

# 各对象类型在领域树下的子目录名
SUBDIR_OPERATION = "运营"
SUBDIR_MEETING = "会议"
SUBDIR_DEV_TICKET = "开发交付"
SUBDIR_RULES = "03-业务规则"
SUBDIR_DELIVERABLE = "05-交付物"


def resolve_domain_path(db, domain_code: str) -> str:
    """返回某领域在 vault 下的相对根目录：01-业务知识/{domain_group}/{domain_name}。

    这是领域相关笔记落盘位置的唯一权威来源，所有 sediment_* 函数都应经此解析，
    不得再硬编码 `01-业务知识/{group}/{name}`。
    """
    domain = db.query(PmwbBusinessDomain).filter(
        PmwbBusinessDomain.domain_code == domain_code
    ).first()
    if not domain:
        raise NotFoundException(message=f"业务领域不存在：{domain_code}")
    return f"{BUSINESS_KNOWLEDGE_DIR}/{domain.domain_group}/{domain.domain_name}"


def operation_dir(db, domain_code: str) -> str:
    """运营工单沉淀目录（相对 vault）。"""
    return f"{resolve_domain_path(db, domain_code)}/{SUBDIR_OPERATION}"


def meeting_dir(db, domain_code: str) -> str:
    """会议纪要沉淀目录（相对 vault）。"""
    return f"{resolve_domain_path(db, domain_code)}/{SUBDIR_MEETING}"


def dev_ticket_dir(db, domain_code: str) -> str:
    """开发工单沉淀目录（相对 vault）。"""
    return f"{resolve_domain_path(db, domain_code)}/{SUBDIR_DEV_TICKET}"
