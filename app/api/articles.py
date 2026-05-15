# -*- coding: utf-8 -*-
"""
文章API
提供文章的增删改查接口
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.middleware import get_current_user
from app.database import get_db
from app.models import Article, ArticleStatus, User

router = APIRouter()


# ==================== 请求/响应模型 ====================


class ArticleResponse(BaseModel):
    """文章响应"""
    id: int
    title: str
    url: str
    source: str
    source_name: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    tags: Optional[str] = None
    score: Optional[float] = None
    keywords: Optional[str] = None
    status: str
    is_pushed: bool
    is_pushed_immediate: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    published_at: Optional[str] = None
    similarity: Optional[float] = None

    class Config:
        from_attributes = True


class ArticleListResponse(BaseModel):
    """文章列表响应"""
    items: List[ArticleResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ArticleUpdateRequest(BaseModel):
    """文章更新请求"""
    status: Optional[str] = None
    tags: Optional[str] = None
    score: Optional[float] = None


# ==================== 辅助函数 ====================


def _to_iso(value) -> Optional[str]:
    """将 datetime 转换为 ISO 格式字符串"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _build_semantic_cache_key(
    keyword: str,
    source: Optional[str],
    status_filter: Optional[str],
    min_score: Optional[float],
    max_score: Optional[float],
    start_date: Optional[str],
    end_date: Optional[str],
    sort_weights: tuple[float, float],
) -> str:
    """
    生成语义搜索缓存键

    Args:
        keyword: 搜索关键词
        source: 来源筛选
        status_filter: 状态筛选
        min_score: 最低评分
        max_score: 最高评分
        start_date: 开始日期
        end_date: 结束日期
        sort_weights: (相似度权重, 评分权重)

    Returns:
        缓存键字符串
    """
    import hashlib

    # 构建键字符串
    key_parts = [
        f"keyword={keyword}",
        f"source={source}",
        f"status={status_filter}",
        f"min_score={min_score}",
        f"max_score={max_score}",
        f"start_date={start_date}",
        f"end_date={end_date}",
        f"weights={sort_weights[0]:.1f},{sort_weights[1]:.1f}",
    ]
    key_str = "|".join(key_parts)

    # 使用 MD5 哈希（缓存键不需要加密安全性）
    return f"semantic_search_{hashlib.md5(key_str.encode()).hexdigest()}"


def _build_article_response(article: Article, similarity: Optional[float] = None) -> dict:
    """构建文章响应字典"""
    return {
        "id": article.id,
        "title": article.title,
        "url": article.url,
        "source": article.source,
        "source_name": article.source_name,
        "content": getattr(article, 'content', None),
        "summary": article.summary,
        "tags": article.tags,
        "score": article.score,
        "keywords": article.keywords,
        "status": article.status,
        "is_pushed": article.is_pushed,
        "is_pushed_immediate": getattr(article, 'is_pushed_immediate', False),
        "created_at": _to_iso(article.created_at),
        "updated_at": _to_iso(article.updated_at),
        "published_at": _to_iso(article.published_at),
        "similarity": similarity,
    }


# ==================== 文章端点 ====================


@router.get("/", response_model=ArticleListResponse)
async def get_articles(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    source: Optional[str] = Query(None, description="来源筛选"),
    status_filter: Optional[str] = Query(None, description="状态筛选", alias="status"),
    min_score: Optional[float] = Query(None, ge=0, le=100, description="最低评分"),
    max_score: Optional[float] = Query(None, ge=0, le=100, description="最高评分"),
    start_date: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    sort_by: str = Query("created_at", description="排序字段"),
    sort_order: str = Query("desc", description="排序方向 (asc/desc)"),
    search_mode: str = Query("keyword", description="搜索模式: keyword/semantic"),
    sort_weight_similarity: float = Query(0.7, ge=0, le=1, description="语义搜索相似度权重"),
    sort_weight_score: float = Query(0.3, ge=0, le=1, description="语义搜索评分权重"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取文章列表

    支持分页、筛选、排序和搜索
    search_mode=keyword: SQL LIKE 模糊搜索（默认）
    search_mode=semantic: 向量语义搜索
    """
    if search_mode not in ("keyword", "semantic"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="search_mode 必须为 keyword 或 semantic"
        )

    if search_mode == "semantic":
        return await _semantic_search_articles(
            db=db,
            page=page,
            page_size=page_size,
            source=source,
            status_filter=status_filter,
            min_score=min_score,
            max_score=max_score,
            start_date=start_date,
            end_date=end_date,
            keyword=keyword,
            sort_weights=(sort_weight_similarity, sort_weight_score),
        )

    return await _keyword_search_articles(
        db=db,
        page=page,
        page_size=page_size,
        source=source,
        status_filter=status_filter,
        min_score=min_score,
        max_score=max_score,
        start_date=start_date,
        end_date=end_date,
        keyword=keyword,
        sort_by=sort_by,
        sort_order=sort_order,
    )


async def _keyword_search_articles(
    db: AsyncSession,
    page: int,
    page_size: int,
    source: Optional[str],
    status_filter: Optional[str],
    min_score: Optional[float],
    max_score: Optional[float],
    start_date: Optional[str],
    end_date: Optional[str],
    keyword: Optional[str],
    sort_by: str,
    sort_order: str,
) -> ArticleListResponse:
    """关键词搜索文章（SQL LIKE 模糊搜索）"""
    conditions = []

    if source:
        conditions.append(Article.source_name == source)

    if status_filter:
        conditions.append(Article.status == status_filter)

    if min_score is not None:
        conditions.append(Article.score >= min_score)

    if max_score is not None:
        conditions.append(Article.score <= max_score)

    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            conditions.append(Article.created_at >= start_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="日期格式错误，请使用 YYYY-MM-DD 格式"
            )

    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date)
            end_dt = end_dt.replace(hour=23, minute=59, second=59)
            conditions.append(Article.created_at <= end_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="日期格式错误，请使用 YYYY-MM-DD 格式"
            )

    if keyword:
        conditions.append(
            or_(
                Article.title.contains(keyword),
                Article.summary.contains(keyword),
                Article.tags.contains(keyword),
            )
        )

    query = select(Article)
    if conditions:
        query = query.where(and_(*conditions))

    count_query = select(func.count(Article.id))
    if conditions:
        count_query = count_query.where(and_(*conditions))

    total = await db.scalar(count_query)

    sort_column = getattr(Article, sort_by, Article.created_at)
    if sort_order.lower() == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(sort_column)

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    articles = result.scalars().all()

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return ArticleListResponse(
        items=[ArticleResponse(**_build_article_response(article)) for article in articles],
        total=total or 0,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


async def _semantic_search_articles(
    db: AsyncSession,
    page: int,
    page_size: int,
    source: Optional[str],
    status_filter: Optional[str],
    min_score: Optional[float],
    max_score: Optional[float],
    start_date: Optional[str],
    end_date: Optional[str],
    keyword: Optional[str],
    sort_weights: tuple[float, float] = (0.7, 0.3),
) -> ArticleListResponse:
    """语义搜索文章（基于向量相似度，带缓存）"""
    import logging
    logger = logging.getLogger(__name__)

    from app.services.vector import vector_service
    from app.services.vector import embedding_manager
    from app.services.vector.vector_db_manager import vector_db_manager
    from app.services.vector.schemas import SearchFilters
    from app.services.vector.semantic_search_cache import semantic_search_cache
    from app.config import get_settings

    if not vector_db_manager.is_available() or not embedding_manager.is_available():
        logger.warning("语义搜索不可用：向量数据库或 Embedding 模型未就绪")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="语义搜索不可用：向量数据库或 Embedding 模型未就绪"
        )

    if not keyword:
        logger.info("语义搜索无关键词，降级到关键词搜索")
        return await _keyword_search_articles(
            db=db, page=page, page_size=page_size,
            source=source, status_filter=status_filter,
            min_score=min_score, max_score=max_score,
            start_date=start_date, end_date=end_date,
            keyword=keyword, sort_by="created_at", sort_order="desc",
        )

    # 生成缓存键
    cache_key = _build_semantic_cache_key(
        keyword=keyword,
        source=source,
        status_filter=status_filter,
        min_score=min_score,
        max_score=max_score,
        start_date=start_date,
        end_date=end_date,
        sort_weights=sort_weights,
    )

    # 尝试从缓存获取
    cached_results = semantic_search_cache.get(cache_key)

    if cached_results is not None:
        logger.info("语义搜索缓存命中: %s", cache_key[:30])
        results = cached_results
    else:
        logger.info("语义搜索缓存未命中: %s", cache_key[:30])

        # 构建过滤条件
        filters = SearchFilters(
            score_min=int(min_score) if min_score is not None else None,
            score_max=int(max_score) if max_score is not None else None,
            status=status_filter or "processed",
            source_type=source,
        )
        if start_date:
            try:
                filters.date_from = datetime.fromisoformat(start_date)
            except ValueError:
                raise HTTPException(status_code=400, detail="start_date 格式错误")
        if end_date:
            try:
                filters.date_to = datetime.fromisoformat(end_date).replace(
                    hour=23, minute=59, second=59
                )
            except ValueError:
                raise HTTPException(status_code=400, detail="end_date 格式错误")

        # 获取配置的最大结果数
        settings = get_settings()
        max_results = settings.semantic_search_max_results

        # 执行语义搜索
        try:
            results = await vector_service.search(
                query=keyword,
                top_k=max_results,
                filters=filters,
                sort_weights=sort_weights,
            )
        except Exception as e:
            logger.warning("语义搜索异常: %s", e)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"语义搜索执行失败: {str(e)}"
            )

        # 写入缓存
        semantic_search_cache.set(cache_key, results)
        logger.info("语义搜索结果已缓存: %d 条", len(results))

    # 分页处理
    total = len(results)

    # 语义搜索模式：始终返回全部结果
    # 前端使用 sessionStorage 缓存完整数据，实现 client-side 分页
    # 翻页时直接从缓存读取，无需再次请求后端
    items = [
        ArticleResponse(
            id=r.article_id,
            title=r.title,
            url=r.url,
            source="",
            source_name=r.source_name,
            summary=r.summary,
            score=r.score,
            status="processed",
            is_pushed=False,
            published_at=_to_iso(r.published_at),
            similarity=r.similarity,
        )
        for r in results
    ]

    # 语义搜索的 total_pages 按前端每页 20 条计算，最多显示 5 页
    page_size_for_calc = page_size if page_size else 20
    total_pages = (total + page_size_for_calc - 1) // page_size_for_calc if total > 0 else 0

    logger.info(
        "语义搜索完成: keyword=%s, total=%d, page=%d, page_size=%d, "
        "sort_weights=(%.2f, %.2f), cache_key=%s",
        keyword, total, page, page_size, sort_weights[0], sort_weights[1],
        cache_key[:30]
    )

    return ArticleListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{article_id}", response_model=ArticleResponse)
async def get_article(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取文章详情
    """
    result = await db.execute(
        select(Article).where(Article.id == article_id)
    )
    article = result.scalar_one_or_none()

    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文章不存在"
        )

    return ArticleResponse(**_build_article_response(article))


@router.put("/{article_id}", response_model=ArticleResponse)
async def update_article(
    article_id: int,
    request: ArticleUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    更新文章
    """
    result = await db.execute(
        select(Article).where(Article.id == article_id)
    )
    article = result.scalar_one_or_none()

    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文章不存在"
        )

    # 更新字段
    if request.status is not None:
        article.status = request.status

    if request.tags is not None:
        article.tags = request.tags

    if request.score is not None:
        article.score = request.score

    article.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(article)

    return ArticleResponse(**_build_article_response(article))


@router.delete("/{article_id}")
async def delete_article(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    删除文章
    """
    result = await db.execute(
        select(Article).where(Article.id == article_id)
    )
    article = result.scalar_one_or_none()

    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文章不存在"
        )

    await db.delete(article)
    await db.commit()

    return {"message": "文章已删除"}


@router.post("/{article_id}/reprocess")
async def reprocess_article(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    重新处理文章

    将文章状态重置为待处理，等待重新处理
    """
    result = await db.execute(
        select(Article).where(Article.id == article_id)
    )
    article = result.scalar_one_or_none()

    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文章不存在"
        )

    article.status = ArticleStatus.PENDING.value
    article.updated_at = datetime.utcnow()
    article.tags = None
    article.keywords = None
    article.score = None
    article.is_pushed = None
    article.pushed_at = None

    await db.commit()

    return {"message": "文章已标记为待处理，等待重新处理"}


# ==================== 向量搜索端点 ====================

@router.get("/search/semantic")
async def semantic_search(
    q: str = Query(..., min_length=1, description="搜索词"),
    limit: int = Query(20, ge=1, le=100, description="返回数量"),
    score_min: Optional[int] = Query(None, ge=0, le=100, description="最低评分过滤"),
    date_from: Optional[str] = Query(None, description="最早发布日期 (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="最晚发布日期 (YYYY-MM-DD)"),
    current_user: User = Depends(get_current_user),
):
    """
    语义搜索

    基于向量相似度搜索文章，支持评分和日期过滤。
    """
    from datetime import datetime as dt

    from app.services.vector import vector_service
    from app.services.vector.schemas import SearchFilters

    filters = SearchFilters(score_min=score_min)
    if date_from:
        try:
            filters.date_from = dt.fromisoformat(date_from)
        except ValueError:
            raise HTTPException(status_code=400, detail="date_from 格式错误，使用 YYYY-MM-DD")
    if date_to:
        try:
            filters.date_to = dt.fromisoformat(date_to)
        except ValueError:
            raise HTTPException(status_code=400, detail="date_to 格式错误，使用 YYYY-MM-DD")

    results = await vector_service.search(query=q, top_k=limit, filters=filters)

    return {
        "code": 200,
        "data": [r.model_dump() for r in results],
        "message": "success",
    }


@router.get("/{article_id}/similar")
async def similar_articles(
    article_id: int,
    limit: int = Query(5, ge=1, le=20, description="推荐数量"),
    status: str = Query("processed", description="文章状态过滤"),
    current_user: User = Depends(get_current_user),
):
    """
    相似文章推荐

    基于当前文章的向量检索最相似的其他文章。
    默认只返回 status=processed 的已处理文章。
    """
    from app.services.vector import vector_service

    results = await vector_service.recommend(
        article_id=article_id,
        top_k=limit,
        status_filter=status,
    )

    return {
        "code": 200,
        "data": [r.model_dump() if hasattr(r, "model_dump") else r for r in results],
        "message": "success",
    }