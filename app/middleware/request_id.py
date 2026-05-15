# -*- coding: utf-8 -*-
"""
请求追踪中间件

为每个请求添加唯一 ID，便于日志追踪和问题排查
"""

import uuid
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("request")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    请求 ID 中间件

    为每个请求生成唯一 ID，通过以下方式传递:
    1. request.state.request_id 供业务代码使用
    2. 响应头 X-Request-ID 返回给客户端
    """

    async def dispatch(self, request: Request, call_next):
        # 从请求头获取已有的 request_id，或生成新的
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        # 记录请求开始
        logger.info(
            f"Request started: {request_id} {request.method} {request.url.path}"
        )

        # 处理请求
        response = await call_next(request)

        # 在响应头中返回请求 ID
        response.headers["X-Request-ID"] = request_id

        # 记录请求完成
        logger.info(
            f"Request completed: {request_id} status={response.status_code}"
        )

        return response
