from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.response import success
from db.base import get_db
from schemas.todo import TodoCreate, TodoListResponse, TodoOut, TodoStats, TodoUpdate
from services.todo import todo_service

router = APIRouter(prefix="/todos", tags=["待办中心"])


@router.get("", response_model=TodoListResponse)
def list_todos(
    keyword: Optional[str] = Query(None, description="关键字搜索"),
    category: Optional[str] = Query(None, description="分类"),
    status: Optional[str] = Query(None, description="状态"),
    priority: Optional[str] = Query(None, description="优先级"),
    is_overdue: Optional[bool] = Query(None, description="是否超期"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    db: Session = Depends(get_db),
):
    """查询待办列表。"""
    return todo_service.list_with_filters(
        db=db,
        keyword=keyword,
        category=category,
        status=status,
        priority=priority,
        is_overdue=is_overdue,
        page=page,
        page_size=page_size,
    )


@router.get("/stats", response_model=TodoStats)
def get_stats(db: Session = Depends(get_db)):
    """获取待办统计。"""
    return todo_service.get_stats(db)


@router.get("/{todo_id}", response_model=TodoOut)
def get_todo(todo_id: int, db: Session = Depends(get_db)):
    """获取待办详情。"""
    return todo_service.get(db, todo_id)


@router.post("", response_model=TodoOut)
def create_todo(obj_in: TodoCreate, db: Session = Depends(get_db)):
    """创建待办。"""
    return todo_service.create(db, obj_in.model_dump())


@router.put("/{todo_id}", response_model=TodoOut)
def update_todo(todo_id: int, obj_in: TodoUpdate, db: Session = Depends(get_db)):
    """更新待办。"""
    return todo_service.update(db, todo_id, obj_in.model_dump(exclude_unset=True))


@router.patch("/{todo_id}/status")
def update_todo_status(todo_id: int, status: str, db: Session = Depends(get_db)):
    """更新待办状态。"""
    obj = todo_service.update_status(db, todo_id, status)
    return success(data=obj)


@router.delete("/{todo_id}")
def delete_todo(todo_id: int, db: Session = Depends(get_db)):
    """删除待办。"""
    ok = todo_service.delete(db, todo_id)
    return success(data=ok)
