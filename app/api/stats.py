# -*- coding: utf-8 -*-
"""
统计API
提供系统统计数据接口
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import case, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.middleware import get_current_user
from app.database import get_db
from app.models import Article, GitHubRepo, PushLog, RSSSource, User, WebhookConfig, LLMModel

router = APIRouter()


# ==================== 响应模型 ====================


class BasicStats(BaseModel):
    """基础统计"""
    articles: int = 0
    github_repos: int = 0
    users: int = 0
    rss_sources: int = 0
    my_articles: int = 0
    my_rss_sources: int = 0


class ArticleStats(BaseModel):
    """文章统计"""
    total: int
    today: int
    this_week: int
    avg_score: Optional[float] = None
    by_source: Dict[str, int]
    by_status: Dict[str, int]


class GitHubStats(BaseModel):
    """GitHub统计"""
    total: int
    today: int
    by_language: Dict[str, int]


class UserStats(BaseModel):
    """用户统计"""
    total: int
    active: int
    by_platform: Dict[str, int]


class PushLogStats(BaseModel):
    """推送日志统计"""
    total: int
    success_rate: float
    today: int


class DetailedStats(BaseModel):
    """详细统计"""
    articles: ArticleStats
    github_repos: GitHubStats
    users: UserStats
    push_logs: PushLogStats


class TrendData(BaseModel):
    """趋势数据"""
    dates: List[str]
    articles: List[int]
    github_repos: List[int]
    pushes: List[int]


class RecentArticle(BaseModel):
    """最近文章响应"""
    id: int
    title: str
    url: str
    source: str
    source_name: str = ""
    score: float = 0
    published_at: str = ""


class DashboardStats(BaseModel):
    """完整的Dashboard统计数据"""
    # 基础数量
    articles: int = 0
    github_repos: int = 0
    my_articles: int = 0
    my_rss_sources: int = 0
    # 活跃状态
    active_webhook_count: int = 0
    active_model_count: int = 0
    # 新增：Embedding模型状态
    embedding_model_count: int = 0
    # 最近内容
    recent_articles: List[RecentArticle] = []
    recent_repos: List[dict] = []


# ==================== 统计端点 ====================


@router.get("/", response_model=BasicStats)
async def get_basic_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取基础统计信息
    """
    # 统计文章数量
    article_count = await db.scalar(select(func.count(Article.id)))
    
    # 统计GitHub项目数量
    github_count = await db.scalar(select(func.count(GitHubRepo.id)))
    
    # 统计用户数量
    user_count = await db.scalar(select(func.count(User.id)))
    
    # 统计RSS源数量
    rss_count = await db.scalar(select(func.count(RSSSource.id)))
    
    return BasicStats(
        articles=article_count or 0,
        github_repos=github_count or 0,
        users=user_count or 0,
        rss_sources=rss_count or 0,
    )


@router.get("/detailed", response_model=DetailedStats)
async def get_detailed_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取详细统计信息

    优化: 使用条件聚合减少数据库往返
    """
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today - timedelta(days=7)

    # ===== 文章统计优化: 使用条件聚合一次查询 =====
    article_stats_result = await db.execute(
        select(
            func.count(Article.id).label('total'),
            func.count(case((Article.created_at >= today, 1))).label('today'),
            func.count(case((Article.created_at >= week_ago, 1))).label('this_week'),
            func.avg(Article.score).label('avg_score'),
        )
    )
    article_stats = article_stats_result.one()
    article_total = article_stats.total or 0
    article_today = article_stats.today or 0
    article_this_week = article_stats.this_week or 0
    avg_score = article_stats.avg_score

    # 按来源统计
    source_result = await db.execute(
        select(Article.source_name, func.count(Article.id))
        .group_by(Article.source_name)
    )
    by_source = {row[0]: row[1] for row in source_result.all()}

    # 按状态统计
    status_result = await db.execute(
        select(Article.status, func.count(Article.id))
        .group_by(Article.status)
    )
    by_status = {row[0]: row[1] for row in status_result.all()}

    # ===== GitHub统计优化: 使用条件聚合 =====
    github_stats_result = await db.execute(
        select(
            func.count(GitHubRepo.id).label('total'),
            func.count(case((GitHubRepo.created_at >= today, 1))).label('today'),
        )
    )
    github_stats = github_stats_result.one()
    github_total = github_stats.total or 0
    github_today = github_stats.today or 0

    # 按语言统计
    language_result = await db.execute(
        select(GitHubRepo.language, func.count(GitHubRepo.id))
        .where(GitHubRepo.language.isnot(None))
        .group_by(GitHubRepo.language)
    )
    by_language = {row[0]: row[1] for row in language_result.all()}

    # ===== 用户统计优化: 使用条件聚合 =====
    user_stats_result = await db.execute(
        select(
            func.count(User.id).label('total'),
            func.count(case((User.is_active == True, 1))).label('active'),
        )
    )
    user_stats = user_stats_result.one()
    user_total = user_stats.total or 0
    user_active = user_stats.active or 0

    # 按平台统计
    platform_result = await db.execute(
        select(User.platform, func.count(User.id))
        .group_by(User.platform)
    )
    by_platform = {row[0]: row[1] for row in platform_result.all()}

    # ===== 推送日志统计优化: 使用条件聚合 =====
    push_stats_result = await db.execute(
        select(
            func.count(PushLog.id).label('total'),
            func.count(case((PushLog.is_success == True, 1))).label('success'),
            func.count(case((PushLog.pushed_at >= today, 1))).label('today'),
        )
    )
    push_stats = push_stats_result.one()
    push_total = push_stats.total or 0
    push_success = push_stats.success or 0
    push_today = push_stats.today or 0

    success_rate = push_success / push_total if push_total > 0 else 0.0

    return DetailedStats(
        articles=ArticleStats(
            total=article_total,
            today=article_today,
            this_week=article_this_week,
            avg_score=float(avg_score) if avg_score else None,
            by_source=by_source,
            by_status=by_status,
        ),
        github_repos=GitHubStats(
            total=github_total,
            today=github_today,
            by_language=by_language,
        ),
        users=UserStats(
            total=user_total,
            active=user_active,
            by_platform=by_platform,
        ),
        push_logs=PushLogStats(
            total=push_total,
            success_rate=success_rate,
            today=push_today,
        ),
    )


@router.get("/trends", response_model=TrendData)
async def get_trend_data(
    days: int = Query(30, ge=1, le=365, description="天数"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取趋势数据
    """
    end_date = datetime.utcnow().replace(hour=23, minute=59, second=59, microsecond=0)
    start_date = (end_date - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
    
    # 生成日期列表
    dates = []
    current_date = start_date
    while current_date <= end_date:
        dates.append(current_date.strftime("%Y-%m-%d"))
        current_date += timedelta(days=1)
    
    # 获取每日文章数量
    article_result = await db.execute(
        select(
            func.date(Article.created_at).label("date"),
            func.count(Article.id).label("count")
        )
        .where(Article.created_at >= start_date, Article.created_at <= end_date)
        .group_by(func.date(Article.created_at))
    )
    article_counts = {row.date: row.count for row in article_result.all()}
    
    # 获取每日GitHub项目数量
    github_result = await db.execute(
        select(
            func.date(GitHubRepo.created_at).label("date"),
            func.count(GitHubRepo.id).label("count")
        )
        .where(GitHubRepo.created_at >= start_date, GitHubRepo.created_at <= end_date)
        .group_by(func.date(GitHubRepo.created_at))
    )
    github_counts = {row.date: row.count for row in github_result.all()}
    
    # 获取每日推送数量
    push_result = await db.execute(
        select(
            func.date(PushLog.pushed_at).label("date"),
            func.count(PushLog.id).label("count")
        )
        .where(PushLog.pushed_at >= start_date, PushLog.pushed_at <= end_date)
        .group_by(func.date(PushLog.pushed_at))
    )
    push_counts = {row.date: row.count for row in push_result.all()}
    
    # 填充数据
    articles = [article_counts.get(date, 0) for date in dates]
    github_repos = [github_counts.get(date, 0) for date in dates]
    pushes = [push_counts.get(date, 0) for date in dates]
    
    return TrendData(
        dates=dates,
        articles=articles,
        github_repos=github_repos,
        pushes=pushes,
    )


# ==================== Dashboard 端点 ====================


def _to_iso(value) -> Optional[str]:
    """将 datetime 转换为 ISO 格式字符串"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _build_recent_article(a) -> dict:
    """构建最近文章响应字典"""
    return {
        "id": a.id,
        "title": a.title,
        "url": a.url,
        "source": a.source,
        "source_name": a.source_name or "",
        "score": a.score or 0,
        "published_at": _to_iso(a.published_at) or "",
    }


def _build_recent_repo(r) -> dict:
    """构建最近 GitHub 项目响应字典"""
    return {
        "id": r.id,
        "full_name": r.full_name,
        "url": r.url,
        "language": r.language or "",
        "stars": r.stars,
        "description": r.description or "",
    }


def _build_recent_article_model(a) -> RecentArticle:
    """构建最近文章 Pydantic 模型"""
    return RecentArticle(
        id=a.id,
        title=a.title,
        url=a.url,
        source=a.source,
        source_name=a.source_name or "",
        score=a.score or 0,
        published_at=_to_iso(a.published_at) or "",
    )


@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取完整的Dashboard统计数据

    返回所有Dashboard页面需要的数据，一次请求完成
    """
    # 统计文章数
    article_count = await db.scalar(select(func.count(Article.id))) or 0

    # 统计 GitHub 项目数
    github_repo_count = await db.scalar(select(func.count(GitHubRepo.id))) or 0

    # 统计 RSS 源数
    rss_source_count = await db.scalar(select(func.count(RSSSource.id))) or 0

    # 我的文章数（简化处理：所有文章）
    my_articles = article_count

    # 我的RSS源数（简化处理：所有RSS源）
    my_rss_sources = rss_source_count

    # 统计活跃 Webhook 配置数
    active_webhook_count = await db.scalar(
        select(func.count(WebhookConfig.id)).where(WebhookConfig.is_active == True)
    ) or 0

    # 统计活跃模型数
    active_model_count = await db.scalar(
        select(func.count(LLMModel.id)).where(LLMModel.is_active == True)
    ) or 0

    # 新增：统计已启用的Embedding模型数
    # 延迟导入避免循环依赖
    from app.services.vector import embedding_manager
    embedding_model_count = embedding_manager.get_active_model_count()

    # 获取最近的文章
    recent_articles_result = await db.execute(
        select(Article)
        .order_by(Article.created_at.desc())
        .limit(10)
    )
    recent_articles_list = recent_articles_result.scalars().all()

    recent_articles = [_build_recent_article_model(a) for a in recent_articles_list]

    # 获取最近的 GitHub 项目
    recent_repos_result = await db.execute(
        select(GitHubRepo)
        .order_by(GitHubRepo.stars.desc())
        .limit(10)
    )
    recent_repos_list = recent_repos_result.scalars().all()

    recent_repos = [_build_recent_repo(r) for r in recent_repos_list]

    return DashboardStats(
        articles=article_count,
        github_repos=github_repo_count,
        my_articles=my_articles,
        my_rss_sources=my_rss_sources,
        active_webhook_count=active_webhook_count,
        active_model_count=active_model_count,
        embedding_model_count=embedding_model_count,
        recent_articles=recent_articles,
        recent_repos=recent_repos,
    )


# ==================== 向量统计端点 ====================

@router.get("/vector")
async def vector_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    向量系统统计

    返回向量库和 Embedding 服务的运行状态、24h 缓存命中率等。
    """
    from app.services.vector import vector_db_manager, embedding_manager
    from app.models import Article
    from datetime import datetime, timedelta, timezone

    cutoff_24h = datetime.now(timezone.utc) - timedelta(hours=24)

    total_processed_result = await db.execute(
        select(func.count(Article.id)).where(
            Article.status == "processed",
            Article.updated_at >= cutoff_24h,
        )
    )
    total_processed = total_processed_result.scalar() or 0

    cache_hits_result = await db.execute(
        select(func.count(Article.id)).where(
            Article.cache_hit == True,
            Article.updated_at >= cutoff_24h,
        )
    )
    cache_hits = cache_hits_result.scalar() or 0

    cache_hit_rate = (cache_hits / total_processed * 100) if total_processed > 0 else 0.0

    return {
        "code": 200,
        "data": {
            "vector_db_available": vector_db_manager.is_available(),
            "active_embedding_models": embedding_manager.get_active_model_count(),
            "cache_hit_rate_24h": round(cache_hit_rate, 1),
            "total_processed_24h": total_processed,
            "cache_hits_24h": cache_hits,
        },
        "message": "success",
    }


@router.get("/clusters/{cluster_id}/articles")
async def cluster_articles(
    cluster_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取聚类包含的文章列表

    Returns:
        {
            "code": 200,
            "data": {
                "cluster": { ... },  # 聚类信息
                "articles": [ ... ]  # 文章列表
            }
        }
    """
    import json

    from app.models import ClusterTopic, ClusterArticle, Article

    # 1. 获取聚类信息
    result = await db.execute(
        select(ClusterTopic).where(ClusterTopic.id == cluster_id)
    )
    cluster = result.scalar_one_or_none()

    if not cluster:
        return {"code": 404, "message": "聚类不存在"}

    # 2. 获取关联的文章ID
    article_ids_result = await db.execute(
        select(ClusterArticle.article_id)
        .where(ClusterArticle.cluster_id == cluster_id)
    )
    article_ids = [row[0] for row in article_ids_result.fetchall()]

    # 3. 获取文章详情
    articles = []
    if article_ids:
        articles_result = await db.execute(
            select(Article)
            .where(Article.id.in_(article_ids))
        )
        articles = articles_result.scalars().all()

    return {
        "code": 200,
        "data": {
            "cluster": {
                "id": cluster.id,
                "date": cluster.cluster_date.isoformat() if cluster.cluster_date else None,
                "keywords": json.loads(cluster.keywords) if cluster.keywords else [],
                "article_count": cluster.article_count,
                "avg_score": cluster.avg_score,
                "hotness": cluster.hotness,
                "is_emerging": cluster.is_emerging,
            },
            "articles": [
                {
                    "id": a.id,
                    "title": a.title,
                    "summary": a.summary,
                    "score": a.score,
                    "url": a.url,
                    "source": a.source,
                    "source_name": getattr(a, 'source_name', ''),
                }
                for a in articles
            ],
        },
        "message": "success",
    }


@router.get("/clusters")
async def cluster_stats(
    days: int = Query(7, ge=1, le=90, description="分析天数"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    聚类趋势数据

    返回最近 N 天的聚类主题列表（按热度降序）。
    """
    import json

    from app.models import ClusterTopic
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(ClusterTopic)
        .where(ClusterTopic.cluster_date >= cutoff)
        .order_by(ClusterTopic.hotness.desc())
    )
    clusters = result.scalars().all()

    return {
        "code": 200,
        "data": [
            {
                "id": c.id,
                "date": c.cluster_date.isoformat() if c.cluster_date else None,
                "keywords": json.loads(c.keywords) if c.keywords else [],
                "article_count": c.article_count,
                "avg_score": c.avg_score,
                "hotness": c.hotness,
                "is_emerging": c.is_emerging,
            }
            for c in clusters
        ],
        "message": "success",
    }
