from typing import Any, Dict, Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ResponseModel(BaseModel, Generic[T]):
    code: int = 0
    message: str = "success"
    data: Optional[T] = None


def success(data: Any = None, message: str = "success") -> Dict[str, Any]:
    return {
        "code": 0,
        "message": message,
        "data": data,
    }


def error(message: str, code: int = 500, data: Any = None) -> Dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "data": data,
    }
