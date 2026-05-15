# -*- coding: utf-8 -*-
"""
认证中间件
提供依赖注入函数，用于获取当前用户和验证权限
"""

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import TokenData, verify_token
from app.database import get_db
from app.models import User

# HTTP Bearer认证方案
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    获取当前登录用户
    
    依赖注入函数，用于需要认证的接口
    
    Args:
        credentials: HTTP Bearer认证凭证
        db: 数据库会话
        
    Returns:
        User: 当前用户对象
        
    Raises:
        HTTPException: 认证失败时抛出401错误
    """
    # 验证Token
    token_data = verify_token(credentials.credentials, token_type="access")
    
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 从数据库查询用户
    if token_data.user_id:
        result = await db.execute(
            select(User).where(User.id == token_data.user_id)
        )
    else:
        result = await db.execute(
            select(User).where(User.name == token_data.username)
        )
    
    user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用",
        )
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    获取当前活跃用户
    
    确保用户处于激活状态
    
    Args:
        current_user: 当前用户
        
    Returns:
        User: 活跃的用户对象
        
    Raises:
        HTTPException: 用户被禁用时抛出403错误
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用"
        )
    return current_user


async def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """
    获取可选的当前用户
    
    用于可选认证的接口（某些接口允许匿名访问）
    
    Args:
        credentials: HTTP Bearer认证凭证（可选）
        db: 数据库会话
        
    Returns:
        Optional[User]: 当前用户对象，未认证返回None
    """
    if credentials is None:
        return None
    
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    要求管理员权限
    
    依赖注入函数，用于需要管理员权限的接口
    
    Args:
        current_user: 当前用户
        
    Returns:
        User: 管理员用户对象
        
    Raises:
        HTTPException: 非管理员时抛出403错误
    """
    # 注意：这里假设User模型有is_admin字段
    # 如果没有，需要根据实际需求调整权限判断逻辑
    if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    return current_user
