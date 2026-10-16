"""状态元数据路由：把「状态注册表」暴露给前端（唯一真相源）。

前端启动时拉取一次并缓存，用于渲染徽标 label/tone、筛选下拉、流转下拉可选目标、
总览矩阵列与邮件/详情文案。新增状态后只需改 backend/constants/status_registry.py，
前端无需改动即可自动兼容。
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from constants import status_registry
from core.response import success
from db.base import get_db
from services import vendor_dev as vendor_dev_service
# 注意：services/basic_data.py 里「模块叫 basic_data、实例叫 basic_data_service」，
# 所以必须导入实例本身，不能 `from services import basic_data as basic_data_service`（那拿到的是模块）。
from services.basic_data import basic_data_service

router = APIRouter(prefix="/meta", tags=["元数据"])


@router.get("/status-domains")
def get_status_domains():
    """全站状态域元数据（状态注册表序列化）。"""
    return success(data=status_registry.as_metadata())


# ---------------------------------------------------------------------------
# 系统别名映射（配置入口在人员中台；本路由只提供「只读候选集」给配置下拉用）
#
# 2026-10-16 下线说明：原 /meta/vendor-teams 四个字典端点已删除。映射不再由
# 本地字典 pmwb_vendor_team 承载，改由**人员中台组织管理**的 org_type /
# target_system_name / aliases 三列承载，维护入口：/basic-data → 组织管理。
# ---------------------------------------------------------------------------
@router.get("/target-system-options")
def get_target_system_options(db: Session = Depends(get_db)):
    """「目标系统名」完整候选集（前端下拉唯一数据源，**禁自由文本录入**）。

    = 中台 system 类组织的目标名 ∪ 评估表历史 distinct ∪ sent_emails 历史 distinct

    为什么在这里合并而不是在中台：后两张历史表在 yxtyg_db，中台读不到也不应跨库直连。
    为什么要并入历史值：老工单出现过而已被归并的旧称也要能被选到（否则无法配置别名）。

    degraded=true 表示人员中台不可达，此时 data.options 只含本地历史值，
    前端应提示「候选集不含中台组织」。
    """
    return success(data=vendor_dev_service.target_system_options(db))


@router.get("/org-type-options")
def get_org_type_options(db: Session = Depends(get_db)):
    """组织类型合法值。取值域唯一真相源在人员中台，主后端不落第二份。"""
    return success(data=vendor_dev_service.org_type_options(db))


@router.get("/org-mapping-index")
def get_org_mapping_index(db: Session = Depends(get_db)):
    """全量映射索引（只读总览用，供需求页弹窗展示）。

    返回 [{ org_id, org_name, org_type, target_system_name, aliases, sort }, ...]，
    按 (sort, id) 升序；人员中台不可达时返回空列表，前端需提示降级
    （宁可少显示，也不要把「无映射」误显示成「有映射」）。
    """
    return success(data=basic_data_service.org_mapping_index(db))
