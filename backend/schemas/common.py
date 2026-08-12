from typing import Any, Dict, Generic, List, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginationParams(BaseModel):
    page: int = 1
    page_size: int = 20


class PaginationResponse(BaseModel, Generic[T]):
    total: int
    page: int
    page_size: int
    pages: int
    items: List[T]

    @classmethod
    def create(cls, total: int, page: int, page_size: int, items: List[T]) -> "PaginationResponse[T]":
        pages = (total + page_size - 1) // page_size if page_size > 0 else 1
        return cls(
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
            items=items,
        )


def parse_sort_params(sort_field: str = "id", sort_order: str = "desc") -> Dict[str, Any]:
    return {"field": sort_field, "order": sort_order}
