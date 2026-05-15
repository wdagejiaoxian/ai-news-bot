# -*- coding: utf-8 -*-
"""
GitHub项目API
提供GitHub项目的查询接口
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.middleware import get_current_user
from app.database import get_db
from app.models import GitHubRepo, User
from app.utils.github_language import normalize_language_name

router = APIRouter()


# ==================== 请求/响应模型 ====================


class GitHubRepoResponse(BaseModel):
    """GitHub项目响应"""
    id: int
    full_name: str
    description: Optional[str] = None
    url: str
    language: Optional[str] = None
    stars: int
    forks: int
    stars_today: int
    summary: Optional[str] = None
    tags: Optional[str] = None
    score: Optional[float] = None
    keywords: Optional[str] = None
    trending_date: Optional[str] = None
    trending_range: str
    status: str
    is_pushed: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class GitHubRepoListResponse(BaseModel):
    """GitHub项目列表响应"""
    items: List[GitHubRepoResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ==================== 辅助函数 ====================


def _to_iso(value) -> Optional[str]:
    """将 datetime 转换为 ISO 格式字符串"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _build_github_response(repo: GitHubRepo) -> dict:
    """构建 GitHub 项目响应字典"""
    return {
        "id": repo.id,
        "full_name": repo.full_name,
        "description": repo.description,
        "url": repo.url,
        "language": repo.language,
        "stars": repo.stars,
        "forks": repo.forks,
        "stars_today": repo.stars_today,
        "summary": repo.summary,
        "tags": repo.tags,
        "score": repo.score,
        "keywords": repo.keywords,
        "trending_date": _to_iso(repo.trending_date),
        "trending_range": repo.trending_range,
        "status": repo.status,
        "is_pushed": repo.is_pushed,
        "created_at": _to_iso(repo.created_at),
        "updated_at": _to_iso(repo.updated_at),
    }


# ==================== GitHub项目端点 ====================


@router.get("/", response_model=GitHubRepoListResponse)
async def get_github_repos(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    language: Optional[str] = Query(None, description="编程语言筛选"),
    min_stars: Optional[int] = Query(None, ge=0, description="最低Star数"),
    start_date: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    sort_by: str = Query("stars", description="排序字段"),
    sort_order: str = Query("desc", description="排序方向 (asc/desc)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取GitHub项目列表

    支持分页、筛选、排序
    """
    # 构建查询条件
    conditions = []

    if language:
        normalized_language = normalize_language_name(language)
        conditions.append(GitHubRepo.language == normalized_language)

    if min_stars is not None:
        conditions.append(GitHubRepo.stars >= min_stars)

    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            conditions.append(GitHubRepo.trending_date >= start_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="日期格式错误，请使用 YYYY-MM-DD 格式"
            )

    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date)
            end_dt = end_dt.replace(hour=23, minute=59, second=59)
            conditions.append(GitHubRepo.trending_date <= end_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="日期格式错误，请使用 YYYY-MM-DD 格式"
            )

    # 构建查询
    query = select(GitHubRepo)
    if conditions:
        query = query.where(and_(*conditions))

    # 获取总数
    count_query = select(func.count(GitHubRepo.id))
    if conditions:
        count_query = count_query.where(and_(*conditions))

    total = await db.scalar(count_query)

    # 排序
    sort_column = getattr(GitHubRepo, sort_by, GitHubRepo.stars)
    if sort_order.lower() == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(sort_column)

    # 分页
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # 执行查询
    result = await db.execute(query)
    repos = result.scalars().all()

    # 计算总页数
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return GitHubRepoListResponse(
        items=[GitHubRepoResponse(**_build_github_response(repo)) for repo in repos],
        total=total or 0,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{repo_id}", response_model=GitHubRepoResponse)
async def get_github_repo(
    repo_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取GitHub项目详情
    """
    result = await db.execute(
        select(GitHubRepo).where(GitHubRepo.id == repo_id)
    )
    repo = result.scalar_one_or_none()

    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )

    return GitHubRepoResponse(**_build_github_response(repo))