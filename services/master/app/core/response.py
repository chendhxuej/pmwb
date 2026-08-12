from typing import Any, Dict

from fastapi.encoders import jsonable_encoder


def success(data: Any = None, message: str = "success") -> Dict[str, Any]:
    return {
        "code": 0,
        "message": message,
        "data": jsonable_encoder(data) if data is not None else None,
    }


def error(message: str, code: int = 500, data: Any = None) -> Dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "data": jsonable_encoder(data) if data is not None else None,
    }
