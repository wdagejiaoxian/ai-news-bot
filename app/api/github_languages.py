# -*- coding: utf-8 -*-
"""
GitHub语言配置API
提供GitHub采集语言的增删改查接口
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.middleware import get_current_user
from app.database import db, get_db
from app.models import GitHubLanguage, User
from app.utils.github_language import normalize_language_name

router = APIRouter()


# ==================== 请求/响应模型 ====================

class GitHubLanguageResponse(BaseModel):
    id: int
    name: str
    color: Optional[str] = None
    is_active: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class GitHubLanguageListResponse(BaseModel):
    items: List[GitHubLanguageResponse]
    total: int


class GitHubLanguageCreateRequest(BaseModel):
    name: str
    color: Optional[str] = None
    is_active: bool = True


class GitHubLanguageUpdateRequest(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    is_active: Optional[bool] = None


# ==================== 辅助函数 ====================

def validate_github_language(language_name: str) -> bool:
    """
    校验语言是否是有效的GitHub语言

    Args:
        language_name: 语言名称

    Returns:
        bool: 是否有效
    """
    from gtrending import check_language
    return check_language(language_name)


# ==================== 端点 ====================

@router.get("/", response_model=GitHubLanguageListResponse)
async def get_github_languages(
    is_active: Optional[bool] = Query(None, description="激活状态筛选"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取GitHub语言配置列表"""
    query = select(GitHubLanguage)

    if is_active is not None:
        query = query.where(GitHubLanguage.is_active == is_active)

    query = query.order_by(GitHubLanguage.created_at.desc())

    result = await db.execute(query)
    languages = result.scalars().all()

    return GitHubLanguageListResponse(
        items=[
            GitHubLanguageResponse(
                id=lang.id,
                name=lang.name,
                color=lang.color,
                is_active=lang.is_active,
                created_at=lang.created_at.isoformat() if lang.created_at else None,
                updated_at=lang.updated_at.isoformat() if lang.updated_at else None,
            )
            for lang in languages
        ],
        total=len(languages),
    )


@router.post("/", response_model=GitHubLanguageResponse)
async def create_github_language(
    request: GitHubLanguageCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建GitHub语言配置"""
    # 0. 标准化语言名称为首字母大写
    normalized_name = normalize_language_name(request.name)

    # 1. 校验语言是否有效（调用 GitHub Trending API 验证）
    if not validate_github_language(normalized_name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的 GitHub 语言: {normalized_name}"
        )

    # 2. 检查是否已存在于数据库
    result = await db.execute(
        select(GitHubLanguage).where(GitHubLanguage.name == normalized_name)
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该语言已存在"
        )

    # 3. 创建语言配置
    language = GitHubLanguage(
        name=normalized_name,
        color=request.color,
        is_active=request.is_active,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    db.add(language)
    await db.commit()
    await db.refresh(language)

    return GitHubLanguageResponse(
        id=language.id,
        name=language.name,
        color=language.color,
        is_active=language.is_active,
        created_at=language.created_at.isoformat() if language.created_at else None,
        updated_at=language.updated_at.isoformat() if language.updated_at else None,
    )


@router.put("/{language_id}", response_model=GitHubLanguageResponse)
async def update_github_language(
    language_id: int,
    request: GitHubLanguageUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新GitHub语言配置"""
    result = await db.execute(
        select(GitHubLanguage).where(GitHubLanguage.id == language_id)
    )
    language = result.scalar_one_or_none()

    if not language:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="语言不存在"
        )

    # 如果 name 被修改，校验新 name 是否有效
    if request.name is not None and request.name != language.name:
        # 标准化语言名称为首字母大写
        normalized_name = normalize_language_name(request.name)

        if not validate_github_language(normalized_name):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"无效的 GitHub 语言: {normalized_name}"
            )

        # 检查新 name 是否与其他记录冲突
        existing_result = await db.execute(
            select(GitHubLanguage).where(
                GitHubLanguage.name == normalized_name,
                GitHubLanguage.id != language_id
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该语言已存在"
            )

        language.name = normalized_name

    if request.color is not None:
        language.color = request.color

    if request.is_active is not None:
        language.is_active = request.is_active

    language.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(language)

    return GitHubLanguageResponse(
        id=language.id,
        name=language.name,
        color=language.color,
        is_active=language.is_active,
        created_at=language.created_at.isoformat() if language.created_at else None,
        updated_at=language.updated_at.isoformat() if language.updated_at else None,
    )


@router.delete("/{language_id}")
async def delete_github_language(
    language_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除GitHub语言配置"""
    result = await db.execute(
        select(GitHubLanguage).where(GitHubLanguage.id == language_id)
    )
    language = result.scalar_one_or_none()

    if not language:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="语言不存在"
        )

    await db.delete(language)
    await db.commit()

    return {"message": "语言已删除"}


# ==================== 辅助函数 ====================

async def get_active_languages() -> List[str]:
    """
    获取所有激活的GitHub语言列表

    用于定时任务等场景获取要采集的语言
    """
    async with db.get_session() as session:
        result = await session.execute(
            select(GitHubLanguage.name).where(GitHubLanguage.is_active == True)
        )
        languages = result.scalars().all()
        return list(languages)
