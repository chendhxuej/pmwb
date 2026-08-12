"""任务中心路由：全系统待办任务聚合 + 邮件通知/催办。"""

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from core.exceptions import ValidationException
from core.response import success
from db.base import get_db
from schemas.task_center import TaskSendRequest
from services.task_center import task_center_service

router = APIRouter(prefix="/task-center", tags=["任务中心"])


class ContactResolveRequest(BaseModel):
    names: List[str]


@router.get("/stats")
def get_stats(db=Depends(get_db)):
    """任务中心统计：总待办/超期/临期/各来源/各状态计数。"""
    data = task_center_service.get_stats(db)
    return success(data=data)


@router.get("/tasks")
def list_tasks(
    source: Optional[str] = None,
    status: Optional[str] = None,
    only_overdue: bool = False,
    include_done: bool = False,
    keyword: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db=Depends(get_db),
):
    """统一任务列表（来源/状态/超期/关键字筛选 + 分页）。"""
    data = task_center_service.get_tasks(
        db,
        source=source,
        status=status,
        only_overdue=only_overdue,
        include_done=include_done,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return success(data=data)


@router.get("/tasks/{source}/{source_id}")
def get_task_detail(source: str, source_id: str, db=Depends(get_db)):
    """任务详情（含源模块摘要与跳转路由）。"""
    item = task_center_service.get_detail(db, f"{source}:{source_id}")
    if item is None:
        raise ValidationException("任务不存在或已被删除")
    return success(data=item)


@router.post("/resolve-contacts")
def resolve_contacts(req: ContactResolveRequest):
    """按姓名解析邮箱（统一邮件中心通讯录）。"""
    data: Dict[str, str] = task_center_service.resolve_contacts(req.names)
    return success(data=data)


@router.post("/send")
def send_task_email(obj_in: TaskSendRequest, db=Depends(get_db)):
    """发送任务通知/催办邮件（正文自动附任务清单，落 email_records）。"""
    data = task_center_service.send_notification(db, obj_in)
    return success(data=data)
