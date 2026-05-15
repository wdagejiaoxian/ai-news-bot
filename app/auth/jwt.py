# -*- coding: utf-8 -*-
"""
JWT认证模块
提供Token生成、验证和刷新功能
"""

from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from jose import JWTError, jwt
from pydantic import BaseModel

from app.config import get_settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码
    
    Args:
        plain_password: 明文密码
        hashed_password: 哈希后的密码
        
    Returns:
        bool: 密码是否匹配
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """
    获取密码哈希值
    
    Args:
        password: 明文密码
        
    Returns:
        str: 哈希后的密码
    """
    return bcrypt.hashpw(
        password.encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')

# JWT配置
settings = get_settings()
SECRET_KEY = settings.secret_key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes
REFRESH_TOKEN_EXPIRE_DAYS = settings.refresh_token_expire_days


class Token(BaseModel):
    """Token响应模型"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Token数据模型"""
    username: Optional[str] = None
    user_id: Optional[int] = None


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    创建Access Token
    
    Args:
        data: 要编码的数据
        expires_delta: 过期时间增量
        
    Returns:
        str: JWT Token
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    return encoded_jwt


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    创建Refresh Token
    
    Args:
        data: 要编码的数据
        expires_delta: 过期时间增量
        
    Returns:
        str: JWT Refresh Token
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    return encoded_jwt


def verify_token(token: str, token_type: str = "access") -> Optional[TokenData]:
    """
    验证Token
    
    Args:
        token: JWT Token
        token_type: Token类型（access/refresh）
        
    Returns:
        Optional[TokenData]: Token数据，验证失败返回None
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # 检查Token类型
        if payload.get("type") != token_type:
            return None
        
        username: str = payload.get("sub")
        user_id: int = payload.get("user_id")
        
        if username is None:
            return None
        
        return TokenData(username=username, user_id=user_id)
        
    except JWTError:
        return None


def create_token_pair(user_id: int, username: str) -> Token:
    """
    创建Token对（Access Token + Refresh Token）
    
    Args:
        user_id: 用户ID
        username: 用户名
        
    Returns:
        Token: 包含access_token和refresh_token的Token对象
    """
    token_data = {"sub": username, "user_id": user_id}
    
    access_token = create_access_token(data=token_data)
    refresh_token = create_refresh_token(data=token_data)
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )
