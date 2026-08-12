"""SQL脚本库路由：主 CRUD + 统计。

挂在 /api/v1/sql-scripts 下。
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.exceptions import NotFoundException
from core.response import success
from db.base import get_db
from schemas.sql_script import (
    SqlScriptCreate,
    SqlScriptListResponse,
    SqlScriptOut,
    SqlScriptUpdate,
)
from services.sql_script import sql_script_service

router = APIRouter(prefix="/sql-scripts", tags=["SQL脚本库"])


@router.get("")
def list_sql_scripts(
    keyword: Optional[str] = Query(None, description="关键字搜索"),
    category: Optional[str] = Query(None, description="业务线/分类"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=1000, description="每页条数"),
    db: Session = Depends(get_db),
):
    """查询 SQL 脚本列表。"""
    result = sql_script_service.list_with_filters(
        db=db,
        keyword=keyword,
        category=category,
        page=page,
        page_size=page_size,
    )
    return success(data=SqlScriptListResponse(**result).model_dump())


@router.get("/stats")
def sql_scripts_stats(db: Session = Depends(get_db)):
    """看板聚合统计（按分类计数、总条数）。"""
    return success(data=sql_script_service.stats(db))


@router.get("/{script_id}")
def get_sql_script(script_id: int, db: Session = Depends(get_db)):
    """获取 SQL 脚本详情。"""
    obj = sql_script_service.get(db, script_id)
    if not obj:
        raise NotFoundException(f"SQL 脚本不存在：id={script_id}")
    return success(data=SqlScriptOut.model_validate(obj))


@router.post("")
def create_sql_script(obj_in: SqlScriptCreate, db: Session = Depends(get_db)):
    """创建 SQL 脚本。"""
    obj = sql_script_service.create(db, obj_in.model_dump(exclude_unset=True))
    return success(data=SqlScriptOut.model_validate(obj))


@router.put("/{script_id}")
def update_sql_script(
    script_id: int, obj_in: SqlScriptUpdate, db: Session = Depends(get_db)
):
    """更新 SQL 脚本。"""
    obj = sql_script_service.update(
        db, script_id, obj_in.model_dump(exclude_unset=True)
    )
    if not obj:
        raise NotFoundException(f"SQL 脚本不存在：id={script_id}")
    return success(data=SqlScriptOut.model_validate(obj))


@router.delete("/{script_id}")
def delete_sql_script(script_id: int, db: Session = Depends(get_db)):
    """删除 SQL 脚本。"""
    ok = sql_script_service.delete(db, script_id)
    return success(data={"deleted": ok})
