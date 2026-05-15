# -*- coding: utf-8 -*-
"""
统一异常处理器
提供全局异常处理和统一错误响应格式
"""

import logging
from typing import Optional

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

logger = logging.getLogger(__name__)


class ApiException(Exception):
    """自定义 API 异常"""

    def __init__(
        self,
        message: str,
        code: int = 400,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[dict] = None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details
        super().__init__(self.message)


class NotFoundException(ApiException):
    """资源不存在"""

    def __init__(self, message: str = "资源不存在", details: Optional[dict] = None):
        super().__init__(
            message=message,
            code=404,
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class UnauthorizedException(ApiException):
    """未授权"""

    def __init__(self, message: str = "未授权", details: Optional[dict] = None):
        super().__init__(
            message=message,
            code=401,
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=details,
        )


class ForbiddenException(ApiException):
    """禁止访问"""

    def __init__(self, message: str = "禁止访问", details: Optional[dict] = None):
        super().__init__(
            message=message,
            code=403,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class ValidationException(ApiException):
    """验证失败"""

    def __init__(self, message: str = "验证失败", details: Optional[dict] = None):
        super().__init__(
            message=message,
            code=422,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )


def create_error_response(
    message: str,
    code: int = 400,
    details: Optional[dict] = None,
) -> dict:
    """创建统一错误响应格式"""
    response = {
        "code": code,
        "message": message,
        "success": False,
    }
    if details:
        response["details"] = details
    return response


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器到 FastAPI 应用"""

    @app.exception_handler(ApiException)
    async def handle_api_exception(request: Request, exc: ApiException):
        """处理自定义 API 异常"""
        logger.warning(f"API Exception: {exc.message} - {exc.details or ''}")
        return JSONResponse(
            status_code=exc.status_code,
            content=create_error_response(
                message=exc.message,
                code=exc.code,
                details=exc.details,
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        """处理请求验证错误"""
        logger.warning(f"Validation Error: {exc.errors()}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=create_error_response(
                message="请求参数验证失败",
                code=422,
                details={"errors": exc.errors()},
            ),
        )

    @app.exception_handler(SQLAlchemyError)
    async def handle_sqlalchemy_error(request: Request, exc: SQLAlchemyError):
        """处理数据库错误"""
        logger.error(f"Database Error: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=create_error_response(
                message="数据库操作失败",
                code=500,
            ),
        )

    @app.exception_handler(IntegrityError)
    async def handle_integrity_error(request: Request, exc: IntegrityError):
        """处理数据完整性错误（如唯一索引冲突）"""
        logger.warning(f"Integrity Error: {exc}")
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=create_error_response(
                message="数据已存在或违反约束",
                code=409,
            ),
        )

    @app.exception_handler(Exception)
    async def handle_generic_exception(request: Request, exc: Exception):
        """处理所有未捕获的异常"""
        logger.error(f"Unhandled Exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=create_error_response(
                message="服务器内部错误",
                code=500,
            ),
        )