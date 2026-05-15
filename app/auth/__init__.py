# -*- coding: utf-8 -*-
"""
认证模块
提供JWT认证相关功能
"""

from app.auth.jwt import (
    Token,
    TokenData,
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    verify_token,
    create_token_pair,
)
from app.auth.middleware import (
    get_current_user,
    get_current_active_user,
    get_optional_current_user,
    require_admin,
)

__all__ = [
    # JWT相关
    "Token",
    "TokenData",
    "verify_password",
    "get_password_hash",
    "create_access_token",
    "create_refresh_token",
    "verify_token",
    "create_token_pair",
    # 中间件相关
    "get_current_user",
    "get_current_active_user",
    "get_optional_current_user",
    "require_admin",
]
