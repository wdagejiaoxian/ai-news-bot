# -*- coding: utf-8 -*-
"""
认证API
提供登录、Token刷新和用户信息接口
支持 Web 面板用户认证
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import (
    Token,
    TokenData,
    create_token_pair,
    verify_password,
    verify_token,
    get_password_hash,
)
from app.auth.middleware import get_current_user
from app.config import get_settings
from app.database import get_db
from app.api.rate_limit import limiter
from app.models import User

router = APIRouter()


# ==================== 请求/响应模型 ====================


class LoginRequest(BaseModel):
    """登录请求"""
    username: str
    password: str


class RefreshTokenRequest(BaseModel):
    """刷新Token请求"""
    refresh_token: str


class UserInfoResponse(BaseModel):
    """用户信息响应"""
    id: int
    username: str
    is_web_panel_user: bool
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class ApiResponse(BaseModel):
    """统一API响应格式"""
    code: int = 200
    data: Optional[dict] = None
    message: str = "success"


# ==================== 认证端点 ====================


@router.post("/login")
@limiter.limit("5/minute")  # 登录接口限制 5次/分钟，防止暴力破解
async def login(
    request: Request,
    login_request: LoginRequest,
    db: AsyncSession = Depends(get_db)
) -> ApiResponse:
    """
    用户登录

    验证用户名和密码，返回JWT Token对
    支持 Web 面板用户和消息推送用户分离
    """
    # 查询 Web 面板用户
    result = await db.execute(
        select(User).where(
            User.is_web_panel_user == True,
            User.platform_id == login_request.username
        )
    )
    user = result.scalar_one_or_none()

    # 如果不是 Web 面板用户，检查是否是普通用户
    if not user:
        # 查询普通用户（使用 name 字段）
        result = await db.execute(
            select(User).where(User.name == login_request.username)
        )
        user = result.scalar_one_or_none()

        # 验证密码（使用旧的验证方式兼容）
        if user and not verify_password(login_request.password, user.platform_id):
            user = None
    else:
        # Web 面板用户使用 password_hash 验证
        if user.password_hash and not verify_password(login_request.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    # 验证用户存在且密码正确
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 检查用户是否激活
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用",
        )
    
    # 创建Token对
    token_pair = create_token_pair(user_id=user.id, username=user.platform_id)
    
    return ApiResponse(
        code=200,
        data={
            "access_token": token_pair.access_token,
            "refresh_token": token_pair.refresh_token,
            "token_type": token_pair.token_type,
            "expires_in": get_settings().access_token_expire_minutes * 60,  # 与 config 同步
        },
        message="登录成功"
    )


@router.post("/refresh")
async def refresh_token(
    request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
) -> ApiResponse:
    """
    刷新Token
    
    使用Refresh Token获取新的Token对
    """
    # 验证Refresh Token
    token_data = verify_token(request.refresh_token, token_type="refresh")
    
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的Refresh Token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 查询用户
    if token_data.user_id:
        result = await db.execute(
            select(User).where(User.id == token_data.user_id)
        )
    else:
        result = await db.execute(
            select(User).where(User.platform_id == token_data.username)
        )
    
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用",
        )
    
    # 创建新的Token对
    token_pair = create_token_pair(user_id=user.id, username=user.platform_id)
    
    return ApiResponse(
        code=200,
        data={
            "access_token": token_pair.access_token,
            "expires_in": get_settings().access_token_expire_minutes * 60,  # 与 config 同步
        },
        message="刷新成功"
    )


@router.get("/me")
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
) -> ApiResponse:
    """
    获取当前用户信息
    
    需要有效的Access Token
    """
    return ApiResponse(
        code=200,
        data={
            "id": current_user.id,
            "username": current_user.platform_id,
            "is_web_panel_user": current_user.is_web_panel_user,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        },
        message="success"
    )
