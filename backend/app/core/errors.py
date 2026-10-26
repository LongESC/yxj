"""统一异常定义"""

from fastapi import HTTPException, status


class AppError(HTTPException):
    """业务异常基类"""

    def __init__(self, detail: str, code: int = 0, status_code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(status_code=status_code, detail={"message": detail, "code": code})


class UnauthorizedError(AppError):
    def __init__(self, detail: str = "未授权，请先登录"):
        super().__init__(detail=detail, status_code=status.HTTP_401_UNAUTHORIZED)


class ForbiddenError(AppError):
    def __init__(self, detail: str = "权限不足"):
        super().__init__(detail=detail, status_code=status.HTTP_403_FORBIDDEN)


class NotFoundError(AppError):
    def __init__(self, detail: str = "资源不存在"):
        super().__init__(detail=detail, status_code=status.HTTP_404_NOT_FOUND)


class RateLimitError(AppError):
    def __init__(self, detail: str = "请求过于频繁，请稍后再试"):
        super().__init__(detail=detail, status_code=status.HTTP_429_TOO_MANY_REQUESTS)


class ContentSafetyError(AppError):
    def __init__(self, detail: str = "内容包含不当信息，请修改后重试"):
        super().__init__(detail=detail, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
