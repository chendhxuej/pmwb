from typing import Any, Dict, Generic, List, TypeVar

from sqlalchemy.orm import Session

from schemas.common import PaginationParams, PaginationResponse

ModelType = TypeVar("ModelType")


class BaseService(Generic[ModelType]):
    """通用 CRUD Service 基类。"""

    def __init__(self, model: type):
        self.model = model

    def get(self, db: Session, id: int) -> ModelType | None:
        return db.query(self.model).filter(self.model.id == id).first()

    def get_by_ids(self, db: Session, ids: List[int]) -> List[ModelType]:
        return db.query(self.model).filter(self.model.id.in_(ids)).all()

    def list(
        self,
        db: Session,
        filters: Dict[str, Any] | None = None,
        pagination: PaginationParams | None = None,
        order_by: str = "id",
        desc: bool = True,
    ) -> PaginationResponse[ModelType]:
        query = db.query(self.model)
        if filters:
            for key, value in filters.items():
                if value is not None and hasattr(self.model, key):
                    query = query.filter(getattr(self.model, key) == value)

        total = query.count()

        order_column = getattr(self.model, order_by, self.model.id)
        if desc:
            query = query.order_by(order_column.desc())
        else:
            query = query.order_by(order_column.asc())

        if pagination:
            offset = (pagination.page - 1) * pagination.page_size
            query = query.offset(offset).limit(pagination.page_size)

        items = query.all()

        return PaginationResponse.create(
            total=total,
            page=pagination.page if pagination else 1,
            page_size=pagination.page_size if pagination else total,
            items=items,
        )

    def create(self, db: Session, obj_in: Dict[str, Any]) -> ModelType:
        db_obj = self.model(**obj_in)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(self, db: Session, id: int, obj_in: Dict[str, Any]) -> ModelType | None:
        db_obj = self.get(db, id)
        if not db_obj:
            return None
        for key, value in obj_in.items():
            if hasattr(db_obj, key):
                setattr(db_obj, key, value)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: Session, id: int) -> bool:
        db_obj = self.get(db, id)
        if not db_obj:
            return False
        db.delete(db_obj)
        db.commit()
        return True
