# -*- coding: utf-8 -*-
"""
去重和存储模块

负责:
- 基于URL哈希或标题指纹去重
- 存储采集的文章和项目
"""

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import db
from app.models import Article, ArticleStatus, GitHubRepo, RSSSource

logger = logging.getLogger(__name__)


class Deduplicator:
    """
    去重处理器
    
    使用多种策略进行去重:
    1. URL哈希 (SHA256) - 精确匹配
    2. 标题相似度 - 模糊匹配
    
    数据库存储已处理的内容，避免重复采集
    """
    
    def __init__(self):
        pass
    
    def compute_url_hash(self, url: str) -> str:
        """
        计算URL哈希
        
        Args:
            url: 文章URL
        
        Returns:
            str: SHA256哈希值
        """
        return hashlib.sha256(url.encode()).hexdigest()
    
    def compute_title_fingerprint(self, title: str) -> str:
        """
        计算标题指纹
        
        标准化标题后计算哈希
        用于模糊匹配
        
        Args:
            title: 文章标题
        
        Returns:
            str: 标准化后的哈希
        """
        # 标准化: 小写，移除空白和标点
        normalized = (
            title.lower()
            .strip()
            .replace(" ", "")
            .replace("-", "")
            .replace("_", "")
        )
        return hashlib.sha256(normalized.encode()).hexdigest()[:32]
    
    async def is_duplicate_article(self, url: str) -> bool:
        """
        检查文章是否已存在
        
        Args:
            url: 文章URL
        
        Returns:
            bool: 是否已存在
        """
        url_hash = self.compute_url_hash(url)
        
        async with db.get_session() as session:
            # 查询是否存在
            stmt = select(Article).where(Article.url_hash == url_hash)
            result = await session.execute(stmt)
            article = result.scalar_one_or_none()
            
            return article is not None
    
    async def is_duplicate_github_repo(
        self,
        full_name: str,
        date: datetime = None
    ) -> bool:
        """
        检查GitHub项目是否已存在
        
        Args:
            full_name: 仓库全名
            date: 采集日期
        
        Returns:
            bool: 是否已存在
        """
        if date is None:
            date = datetime.utcnow()
        
        # 计算哈希
        content = f"{full_name}-{date.strftime('%Y-%m-%d')}"
        repo_hash = hashlib.sha256(content.encode()).hexdigest()[:64]
        
        async with db.get_session() as session:
            stmt = select(GitHubRepo).where(GitHubRepo.repo_hash == repo_hash)
            result = await session.execute(stmt)
            repo = result.scalar_one_or_none()
            
            return repo is not None
    
    async def save_article(
        self,
        title: str,
        url: str,
        source: str,
        source_name: str,
        summary: str = None,
        content: str = None,
        author: str = None,
        published_at: datetime = None,
    ) -> Optional[Article]:
        """
        保存文章到数据库
        
        如果已存在则返回None
        
        Args:
            title: 标题
            url: 链接
            source: 来源类型
            source_name: 来源名称
            summary: 摘要
            content: 内容
            author: 作者
            published_at: 发布时间
        
        Returns:
            Article or None: 保存的文章，如果已存在返回None
        """
        # 检查是否重复
        if await self.is_duplicate_article(url):
            logger.debug(f"文章已存在，跳过: {title[:30]}...")
            return None
        
        # 创建文章对象
        url_hash = self.compute_url_hash(url)
        
        article = Article(
            title=title[:500],
            url=url,
            url_hash=url_hash,
            source=source,
            source_name=source_name,
            summary=summary,
            content=content,
            author=author,
            published_at=published_at or datetime.utcnow(),
            status=ArticleStatus.PENDING.value,
        )
        
        async with db.get_session() as session:
            session.add(article)
            # session 会在上下文管理器中自动 commit
        
        logger.info(f"保存新文章: {title[:30]}...")
        return article
    
    async def save_github_repo(
            self,
            full_name: str,
            url: str,
            language: str = None,
            description: str = None,
            stars: int = 0,
            forks: int = 0,
            stars_today: int = 0,
            trending_date: datetime = None,
            trending_range: str = "daily",
    ) -> Optional[GitHubRepo]:
        """
        保存GitHub项目到数据库
        
        Args:
            full_name: 仓库全名
            url: 仓库URL
            language: 编程语言
            description: 描述
            stars: 星标数
            forks: Fork数
            stars_today: 今日新增
            trending_date: 采集日期
            trending_range: 时间范围
        
        Returns:
            GitHubRepo or None: 保存的项目，如果已存在返回None
        """
        if trending_date is None:
            trending_date = datetime.now(timezone.utc)
        
        # 计算哈希
        content = f"{full_name}-{url}-{language}-{trending_range}"
        repo_hash = hashlib.sha256(content.encode()).hexdigest()[:64]
        
        # 检查是否重复
        async with db.get_session() as session:
            stmt = select(GitHubRepo).where(GitHubRepo.repo_hash == repo_hash)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            
            if existing:
                # 更新现有记录
                existing.full_name = full_name
                existing.url = url
                existing.repo_hash = repo_hash
                existing.language = language
                existing.description = description
                existing.stars = stars
                existing.forks = forks
                existing.stars_today = stars_today
                existing.trending_date = trending_date
                existing.trending_range = trending_range

                logger.debug(f"GitHub项目已更新: {full_name}")
                await session.commit()
                return existing  # 或 return None 根据业务需求
                # logger.debug(f"GitHub项目已存在，跳过: {full_name}")
                # return None
            else:
                # 创建项目对象
                repo = GitHubRepo(
                    full_name=full_name,
                    url=url,
                    repo_hash=repo_hash,
                    language=language,
                    description=description,
                    stars=stars,
                    forks=forks,
                    stars_today=stars_today,
                    trending_date=trending_date,
                    trending_range=trending_range,
                    status=ArticleStatus.PENDING.value,
                )
                session.add(repo)
                await session.commit()
                logger.info(f"保存新GitHub项目: {full_name}")
                return repo

        # async with db.get_session() as session:
        #     session.add(repo)
        #
        # logger.info(f"保存新GitHub项目: {full_name}")
        # return repo
    
    async def get_recent_articles(
        self,
        limit: int = 20,
        source: List[str] = None,
        status: List[str] = None,
    ) -> List[Article]:
        """
        获取最近的资讯
        
        Args:
            limit: 返回数量
            source: 来源过滤
            status: 状态过滤
        
        Returns:
            List[Article]: 文章列表
        """
        async with db.get_session() as session:
            stmt = select(Article)

            if source:
                stmt = stmt.where(Article.source_name.in_(source))
            if status:
                stmt = stmt.where(Article.status.in_(status))

            stmt = stmt.order_by(
                Article.published_at.desc()
            ).order_by(
                Article.score.desc()
            ).limit(limit)

            result = await session.execute(stmt)
            return list(result.scalars().all())
    
    # async def get_recent_github_repos(
    #     self,
    #     limit: int = 20,
    #     language: str = None,
    #     time_range: str = None,
    # ) -> List[GitHubRepo]:
    #     """
    #     获取最近的GitHub热门项目
    #
    #     Args:
    #         limit: 返回数量
    #         language: 语言过滤
    #         time_range: 时间范围过滤
    #
    #     Returns:
    #         List[GitHubRepo]: 项目列表
    #     """
    #     async with db.get_session() as session:
    #         stmt = select(GitHubRepo)
    #
    #         # 条件过滤
    #         conditions = []
    #         if language:
    #             conditions.append(GitHubRepo.language == language)
    #         if time_range:
    #             conditions.append(GitHubRepo.trending_range == time_range)
    #
    #         if conditions:
    #             stmt = stmt.where(and_(*conditions))
    #
    #         # 排序和限制
    #         stmt = stmt.order_by(GitHubRepo.stars.desc()).limit(limit)
    #
    #         result = await session.execute(stmt)
    #         return list(result.scalars().all())
    
    async def search_articles(
        self,
        keyword: str,
        limit: int = 20,
    ) -> List[Article]:
        """
        搜索文章
        
        模糊匹配标题和摘要
        
        Args:
            keyword: 关键词
            limit: 返回数量
        
        Returns:
            List[Article]: 文章列表
        """
        async with db.get_session() as session:
            # 使用 LIKE 进行模糊搜索
            pattern = f"%{keyword}%"
            stmt = select(Article).where(
                and_(
                    or_(
                        Article.status == ArticleStatus.PROCESSED.value,
                        Article.status == ArticleStatus.PUBLISHED.value,
                    ),
                    or_(
                        Article.title.ilike(pattern),
                        Article.summary.ilike(pattern),
                        Article.content.ilike(pattern),
                        Article.keywords.ilike(pattern),
                    )
                )
            ).order_by(Article.published_at.desc()).order_by(
                Article.score.desc()
            ).limit(limit)
            
            result = await session.execute(stmt)
            return list(result.scalars().all())
    
    async def mark_article_pushed(self, article_id: int) -> bool:
        """
        标记文章已推送
        
        Args:
            article_id: 文章ID
        
        Returns:
            bool: 是否成功
        """
        async with db.get_session() as session:
            stmt = select(Article).where(Article.id == article_id)
            result = await session.execute(stmt)
            article = result.scalar_one_or_none()
            
            if article:
                article.is_pushed = True
                article.pushed_at = datetime.now(timezone.utc)
                article.status = ArticleStatus.PUBLISHED.value
                return True
            
            return False


# 创建全局实例
deduplicator = Deduplicator()
