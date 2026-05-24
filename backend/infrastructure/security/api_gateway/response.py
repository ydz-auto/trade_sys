"""
统一响应格式
"""

import time
from typing import Any, Optional, Dict
from dataclasses import dataclass


@dataclass
class Response:
    status_code: int
    body: Any
    headers: Dict[str, str]


class APIResponse:
    @staticmethod
    def success(
        data: Any = None,
        message: str = "OK",
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        response = {
            "success": True,
            "data": data,
            "message": message,
            "timestamp": int(time.time()),
        }

        if request_id:
            response["request_id"] = request_id

        return response

    @staticmethod
    def error(
        code: int,
        message: str,
        details: Optional[Any] = None,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        response = {
            "success": False,
            "error": {
                "code": code,
                "message": message,
            },
            "timestamp": int(time.time()),
        }

        if details:
            response["error"]["details"] = details

        if request_id:
            response["request_id"] = request_id

        return response

    @staticmethod
    def paginated(
        data: list,
        total: int,
        page: int,
        page_size: int,
        message: str = "OK",
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        response = {
            "success": True,
            "data": {
                "items": data,
                "pagination": {
                    "total": total,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": (total + page_size - 1) // page_size,
                },
            },
            "message": message,
            "timestamp": int(time.time()),
        }

        if request_id:
            response["request_id"] = request_id

        return response

    @staticmethod
    def created(
        data: Any = None,
        message: str = "Created",
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return APIResponse.success(data, message, request_id)

    @staticmethod
    def no_content() -> Dict[str, Any]:
        return {
            "success": True,
            "message": "No Content",
            "timestamp": int(time.time()),
        }


def success_response(
    data: Any = None,
    message: str = "OK",
    request_id: Optional[str] = None,
) -> tuple[Dict[str, Any], int]:
    return APIResponse.success(data, message, request_id), 200


def error_response(
    code: int,
    message: str,
    details: Optional[Any] = None,
    request_id: Optional[str] = None,
) -> tuple[Dict[str, Any], int]:
    return APIResponse.error(code, message, details, request_id), code


def created_response(
    data: Any = None,
    message: str = "Created",
    request_id: Optional[str] = None,
) -> tuple[Dict[str, Any], int]:
    return APIResponse.created(data, message, request_id), 201


def paginated_response(
    data: list,
    total: int,
    page: int,
    page_size: int,
    message: str = "OK",
    request_id: Optional[str] = None,
) -> tuple[Dict[str, Any], int]:
    return APIResponse.paginated(data, total, page, page_size, message, request_id), 200


def no_content_response() -> tuple[Dict[str, Any], int]:
    return APIResponse.no_content(), 204