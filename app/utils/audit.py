# -*- coding: utf-8 -*-
"""
审计日志模块

提供审计装饰器，自动记录敏感操作的日志
"""

import functools
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def audit_log(action: str, resource: str):
    """
    审计日志装饰器

    自动记录操作的执行结果、耗时、用户信息和客户端IP

    Args:
        action: 操作类型 (CREATE, UPDATE, DELETE, LOGIN, LOGOUT, etc.)
        resource: 资源类型 (Article, User, TaskConfig, etc.)

    Usage:
        @router.delete("/articles/{article_id}")
        @audit_log(action="DELETE", resource="Article")
        async def delete_article(...):
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # 提取用户信息
            user = "anonymous"
            for arg in args:
                if hasattr(arg, 'platform_id'):
                    user = getattr(arg, 'platform_id', 'unknown')
                    break
            if not user or user == "anonymous":
                # 尝试从 current_user 参数获取
                if 'current_user' in kwargs:
                    cu = kwargs.get('current_user')
                    if cu:
                        user = getattr(cu, 'platform_id', str(cu))

            # 提取客户端 IP
            ip = "unknown"
            for arg in args:
                if hasattr(arg, 'client'):
                    ip = getattr(arg.client, 'host', 'unknown')
                    break
            if ip == "unknown":
                # 尝试从 request 参数获取
                for arg in args:
                    if hasattr(arg, 'url'):
                        # 这是一个 Request 对象
                        try:
                            ip = arg.client.host if arg.client else "unknown"
                        except:
                            pass

            start_time = datetime.utcnow()

            try:
                result = await func(*args, **kwargs)
                duration = (datetime.utcnow() - start_time).total_seconds()
                logger.info(
                    f"AUDIT | {action} | {resource} | user={user} | ip={ip} | "
                    f"status=success | duration={duration:.3f}s"
                )
                return result
            except Exception as e:
                duration = (datetime.utcnow() - start_time).total_seconds()
                logger.error(
                    f"AUDIT | {action} | {resource} | user={user} | ip={ip} | "
                    f"status=failed | error={str(e)} | duration={duration:.3f}s"
                )
                raise

        return wrapper
    return decorator
