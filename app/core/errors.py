from typing import Any


class AppError(Exception):
    """业务错误：统一映射为 {code, message, details, request_id}。"""

    def __init__(self, code: str, message: str, http_status: int = 400, details: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details = details


class NotFound(AppError):
    def __init__(self, message: str = "资源不存在或不可见") -> None:
        super().__init__("RESOURCE_NOT_FOUND", message, 404)


class Forbidden(AppError):
    def __init__(self, message: str = "缺少权限", code: str = "PERM_FORBIDDEN", details: Any = None) -> None:
        super().__init__(code, message, 403, details)


class Unauthorized(AppError):
    def __init__(self, message: str = "未认证", code: str = "AUTH_TOKEN_EXPIRED") -> None:
        super().__init__(code, message, 401)


class Conflict(AppError):
    def __init__(self, code: str, message: str, details: Any = None) -> None:
        super().__init__(code, message, 409, details)


class ValidationError(AppError):
    def __init__(self, message: str = "字段校验失败", details: Any = None) -> None:
        super().__init__("VALIDATION_FAILED", message, 422, details)
