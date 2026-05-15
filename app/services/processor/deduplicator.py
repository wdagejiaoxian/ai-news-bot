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
from typing import List, Optional, Tuple

from sqlalchemy import select, update, and_, or_
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import get_settings
from app.database import db
from app.models import Article, ArticleStatus, GitHubRepo, RSSSource
from app.utils.github_language import normalize_language_name

logger = logging.getLogger(__name__)

# Phase 4 P4 优化：数据库操作重试配置
_BATCH_SAVE_RETRY_CONFIG = {
    "stop": stop_after_attempt(3),
    "wait": wait_exponential(multiplier=1, min=1, max=10),
    "retry": retry_if_exception_type(OperationalError),
    "reraise": True,
}


class Deduplicator:
    """
    去重处理器

    使用多种策略进行去重:
    1. URL哈希 (BLAKE2b-128) - 精确匹配
    2. 标题相似度 - 模糊匹配

    数据库存储已处理的内容，避免重复采集
    """

    def __init__(self):
        pass

    def compute_url_hash(self, url: str) -> str:
        """
        计算URL哈希 (BLAKE2b-128)

        Args:
            url: 文章URL

        Returns:
            str: BLAKE2b-128哈希值 (16字符hex)
        """
        return hashlib.blake2b(url.encode(), digest_size=8).hexdigest()
    
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

    # Phase 2 P2 优化：IN 子句分片大小（应低于 SQLite 默认上限 999，留有余量）
    _IN_CHUNK_SIZE = 500

    @staticmethod
    async def _query_existing_hashes(
        url_hashes: set,
        session: AsyncSession = None,
    ) -> set:
        """
        分片查询已存在的 url_hash

        当 url_hashes 数量超过 _IN_CHUNK_SIZE 时，分片查询避免
        超出自 SQLITE_MAX_VARIABLE_NUMBER 限制。

        Args:
            url_hashes: 待查询的 url_hash 集合
            session: 可选的共享 session（调用方传入时使用共享事务）

        Returns:
            set: 数据库中已存在的 url_hash 集合
        """
        if not url_hashes:
            return set()

        existing_hashes = set()
        hash_list = list(url_hashes)

        async def check(session: AsyncSession):
            for i in range(0, len(hash_list), Deduplicator._IN_CHUNK_SIZE):
                chunk = hash_list[i:i + Deduplicator._IN_CHUNK_SIZE]
                stmt = select(Article.url_hash).where(Article.url_hash.in_(chunk))
                result = await session.execute(stmt)
                existing_hashes.update(result.scalars().all())

        # 判断是否使用调用方传入的 session
        if session is not None:
            # 使用调用方传入的 session（共享事务）
            await check(session)
        else:
            # 独立 session（自行管理事务）
            async with db.get_session() as session:
                await check(session)

        return existing_hashes

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

    async def batch_check_duplicate_article(
            self,
            articles_data: List[dict]
    ) -> List[dict]:
        # 1. 计算所有文章的 url_hash（在内存中完成，无数据库操作）
        articles_with_hash = []
        url_hashes = set()
        for article_data in articles_data:
            url = article_data["url"]
            url_hash = article_data.get("url_hash",'')
            if not url_hash:
                url_hash = self.compute_url_hash(url)
            articles_with_hash.append((article_data, url_hash))
            url_hashes.add(url_hash)

        # 2. 分片查询已存在的 url_hash（避免 SQLite IN 子句变量上限）
        existing_hashes = await Deduplicator._query_existing_hashes(url_hashes)

        skipped_count = 0
        pass_count = 0
        new_articles = []

        for article_data, url_hash in articles_with_hash:
            if url_hash in existing_hashes:
                logger.debug(f"文章已存在，跳过: {article_data['title'][:30]}...")
                skipped_count += 1
            else:
                new_articles.append(article_data)
                pass_count += 1
                existing_hashes.add(url_hash)  # 防止同批次内重复
        logger.info(f'url哈希查重：重复文章{skipped_count}篇，通过文章{pass_count}篇')
        return new_articles
    
    async def is_duplicate_github_repo(
        self,
        full_name: str,
        url: str,
        language: str = None,
        trending_range: str = "daily",
    ) -> bool:
        """
        检查GitHub项目是否已存在

        Args:
            full_name: 仓库全名
            url: 仓库URL
            language: 编程语言
            trending_range: 时间范围

        Returns:
            bool: 是否已存在
        """
        # 标准化语言
        if language:
            language = normalize_language_name(language)

        # 计算哈希
        repo_hash = self.compute_repo_hash(full_name, url, language, trending_range)

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

    # Phase 4 P4 优化：添加数据库异常重试
    # 仅对 OperationalError（数据库锁超时、连接断开）进行重试
    # IntegrityError（UNIQUE 冲突）和 DataError（数据格式错误）不重试
    @retry(**_BATCH_SAVE_RETRY_CONFIG)
    async def batch_save_articles(
        self,
        articles_data: List[dict],
        skip_url_dedup: bool = False,
    ) -> Tuple[int, int]:
        """
        批量保存文章

        职责：语义去重 + 批量 INSERT（同一事务内）。
        URL 哈希去重由调用方通过 batch_check_duplicate_article() 前置完成，
        或通过 skip_url_dedup=False（默认）在内部完成。

        Args:
            articles_data: 文章数据列表，每项须包含 url_hash, title, url, source, source_name
            skip_url_dedup: 调用方已前置 URL 去重时设为 True（默认 False）

        Returns:
            Tuple[int, int]: (新增数量, 跳过数量)
        """
        if not articles_data:
            return 0, 0

        # 可选的 URL 哈希去重（当 skip_url_dedup=False 时执行）
        url_hashes_to_check = set()
        if not skip_url_dedup:
            for article_data in articles_data:
                uh = article_data.get("url_hash") or self.compute_url_hash(article_data["url"])
                url_hashes_to_check.add(uh)

        # Phase 1 P1 优化：合并 SELECT + INSERT 到同一事务
        # 原因：避免 SELECT 和 INSERT 之间的时间窗口导致竞态条件
        # Phase 2 P2 优化：使用 _query_existing_hashes 分片查询
        # Phase 3 P3 优化：INSERT 分批提交，降低单次事务的锁占用时间
        saved_count = 0
        skipped_count = 0

        async with db.get_session() as session:
            # 如果需要 URL 去重，先查询已存在的哈希（使用共享 session）
            existing_hashes = set()
            if url_hashes_to_check:
                existing_hashes = await Deduplicator._query_existing_hashes(
                    url_hashes_to_check, session=session
                )

            new_articles = []
            for article_data in articles_data:
                url_hash = article_data.get("url_hash") or self.compute_url_hash(article_data["url"])

                # URL 去重判断（仅当未跳过且哈希已存在时跳过）
                if not skip_url_dedup and url_hash in existing_hashes:
                    skipped_count += 1
                    continue

                semantic_duplicate = False
                try:
                    from app.services.vector import vector_service
                    dedup_result = await vector_service.deduplicate(
                        title=article_data.get("title", ""),
                        content=article_data.get("content", ""),
                        summary=article_data.get("summary", ""),
                        rss_source_id=hash(article_data.get("source_name", "")) % 100000 if article_data.get("source_name") else None,
                    )
                    if dedup_result.is_duplicate:
                        logger.info(
                            f"语义去重: {article_data['title'][:30]}... "
                            f"与 article_id={dedup_result.matched_article_id} 重复 "
                            f"(similarity={dedup_result.similarity_score:.3f})"
                        )
                        skipped_count += 1
                        semantic_duplicate = True
                except Exception as e:
                    logger.debug(f"语义去重异常（降级放行）: {e}")

                if semantic_duplicate:
                    continue

                article = Article(
                    title=article_data["title"][:500],
                    url=article_data["url"],
                    url_hash=article_data["url_hash"],
                    source=article_data["source"],
                    source_name=article_data["source_name"],
                    content=article_data.get("content"),
                    author=article_data.get("author"),
                    published_at=article_data.get("published_at") or datetime.utcnow(),
                    status=ArticleStatus.PENDING.value,
                )
                new_articles.append(article)

            # 4. 分批插入（同一事务内，降低锁占用时间）
            if new_articles:
                batch_size = get_settings().article_save_batch_size
                total_count = len(new_articles)
                total_batches = (total_count + batch_size - 1) // batch_size  # 向上取整

                if total_batches > 1:
                    logger.info(
                        f"文章将分 {total_batches} 批保存（每批最多 {batch_size} 篇），"
                        f"共 {total_count} 篇"
                    )

                for i in range(0, total_count, batch_size):
                    batch = new_articles[i:i + batch_size]
                    session.add_all(batch)
                    if total_batches > 1:
                        current_batch = i // batch_size + 1
                        logger.debug(
                            f"第 {current_batch}/{total_batches} 批，"
                            f"插入 {len(batch)} 篇"
                        )

                saved_count = total_count
                logger.info(f"批量保存新文章: {saved_count} 篇")

        return saved_count, skipped_count

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

        # 标准化语言
        if language:
            language = normalize_language_name(language)

        # 计算哈希
        repo_hash = self.compute_repo_hash(full_name, url, language, trending_range)

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
                return existing
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



    def compute_repo_hash(
        self,
        full_name: str,
        url: str,
        language: Optional[str] = None,
        trending_range: str = "daily",
    ) -> str:
        """
        计算GitHub项目的唯一哈希

        Args:
            full_name: 仓库全名
            url: 仓库URL
            language: 编程语言
            trending_range: 时间范围

        Returns:
            str: SHA256哈希值（前64位）
        """
        content = f"{full_name}-{url}-{language}-{trending_range}"
        return hashlib.sha256(content.encode()).hexdigest()[:64]

    @staticmethod
    def escape_like(value: str, escape_char: str = '\\') -> str:
        """
        转义 LIKE 特殊字符，防止注入和全表扫描

        Args:
            value: 原始字符串
            escape_char: 转义字符（默认反斜杠）

        Returns:
            str: 转义后的字符串
        """
        if not value:
            return ""
        # 转义顺序重要：先转义转义字符本身
        value = value.replace(escape_char, escape_char + escape_char)
        value = value.replace('%', escape_char + '%')
        value = value.replace('_', escape_char + '_')
        return value

    async def batch_save_github_repos(
        self,
        repos_data: List[dict],
        default_trending_range: str = "daily",
    ) -> Tuple[int, int]:
        """
        批量保存GitHub项目（去重 + 批量插入/更新）

        采用预计算哈希 + 一次 SELECT ... IN 查询 + 批量操作的方式，
        将 DB 调用次数从 2N 降至 N+1（N=repo数量）。

        Args:
            repos_data: 项目数据列表，每项包含:
                - full_name: 仓库全名
                - url: 仓库URL
                - language: 编程语言
                - description: 描述
                - stars: 星标数
                - forks: Fork数
                - stars_today: 今日新增
                - trending_date: 采集日期
                - trending_range: 时间范围（可选）
            default_trending_range: 默认时间范围

        Returns:
            Tuple[int, int]: (新增数量, 更新数量)
        """
        if not repos_data:
            return 0, 0

        # 1. 预计算所有 repo_hash
        repos_with_hash = []
        repo_hashes = set()
        for repo_data in repos_data:

            language = repo_data.get("language")
            if language:
                language = normalize_language_name(language)
            
            repo_hash = self.compute_repo_hash(
                full_name=repo_data["full_name"],
                url=repo_data["url"],
                language=language,
                trending_range=repo_data.get("trending_range", default_trending_range),
            )
            repos_with_hash.append((repo_data, repo_hash))
            repo_hashes.add(repo_hash)

        # 2. 一次 SELECT ... IN 查询已存在的 repo_hash
        async with db.get_session() as session:
            stmt = select(GitHubRepo.repo_hash).where(GitHubRepo.repo_hash.in_(repo_hashes))
            result = await session.execute(stmt)
            existing_hashes = set(result.scalars().all())

        # 3. 分离新增和更新，在内存中过滤同批次内重复
        new_repos_data = []
        repos_to_update = []
        for repo_data, repo_hash in repos_with_hash:
            if repo_hash in existing_hashes:
                repos_to_update.append((repo_data, repo_hash))
            else:
                new_repos_data.append((repo_data, repo_hash))
                existing_hashes.add(repo_hash)  # 防止同批次内重复

        # 4. 批量操作
        new_count = 0
        updated_count = 0
        if new_repos_data or repos_to_update:
            async with db.get_session() as session:
                # 批量插入新记录
                if new_repos_data:
                    new_repos = []
                    for repo_data, repo_hash in new_repos_data:
                        trending_date = repo_data.get("trending_date")
                        if trending_date is None:
                            trending_date = datetime.now(timezone.utc)

                        language = repo_data.get("language")
                        if language:
                            language = normalize_language_name(language)

                        repo = GitHubRepo(
                            full_name=repo_data["full_name"],
                            url=repo_data["url"],
                            repo_hash=repo_hash,
                            language=language,
                            description=repo_data.get("description"),
                            stars=repo_data.get("stars", 0),
                            forks=repo_data.get("forks", 0),
                            stars_today=repo_data.get("stars_today", 0),
                            trending_date=trending_date,
                            trending_range=repo_data.get("trending_range", default_trending_range),
                            status=ArticleStatus.PENDING.value,
                        )
                        new_repos.append(repo)
                    session.add_all(new_repos)
                    new_count = len(new_repos)

                # 批量更新已存在记录
                if repos_to_update:
                    # 1. 一次 SELECT ... IN 查询所有需要更新的记录，避免 N+1 问题
                    update_hashes = [rh for _, rh in repos_to_update]
                    stmt = select(GitHubRepo).where(GitHubRepo.repo_hash.in_(update_hashes))
                    result = await session.execute(stmt)
                    existing_map = {r.repo_hash: r for r in result.scalars().all()}

                    # 2. 遍历并更新
                    for repo_data, repo_hash in repos_to_update:
                        existing = existing_map.get(repo_hash)
                        if existing:
                            update_language = repo_data.get("language")
                            if update_language:
                                update_language = normalize_language_name(update_language)
                            existing.full_name = repo_data["full_name"]
                            existing.url = repo_data["url"]
                            existing.language = update_language
                            existing.description = repo_data.get("description")
                            existing.stars = repo_data.get("stars", 0)
                            existing.forks = repo_data.get("forks", 0)
                            existing.stars_today = repo_data.get("stars_today", 0)
                            existing.trending_date = repo_data.get("trending_date") or datetime.now(timezone.utc)
                            existing.trending_range = repo_data.get("trending_range", default_trending_range)
                            updated_count += 1

                await session.commit()

        logger.info(f"批量保存GitHub项目完成: 新增 {new_count} 个, 更新 {updated_count} 个")
        return new_count, updated_count
    
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
        # 转义特殊字符并限制长度，防止 LIKE 注入和 DoS
        keyword = (keyword or "")[:100]
        escaped_keyword = self.escape_like(keyword)
        pattern = f"%{escaped_keyword}%"

        async with db.get_session() as session:
            stmt = select(Article).where(
                and_(
                    or_(
                        Article.status == ArticleStatus.PROCESSED.value,
                        Article.status == ArticleStatus.PUBLISHED.value,
                    ),
                    or_(
                        Article.title.ilike(pattern, escape='\\'),
                        Article.summary.ilike(pattern, escape='\\'),
                        Article.content.ilike(pattern, escape='\\'),
                        Article.keywords.ilike(pattern, escape='\\'),
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

    async def mark_articles_pushed(self, article_ids: List[int]) -> int:
        """
        批量标记文章已推送（修复 N 次数据库连接问题）

        Args:
            article_ids: 文章ID列表

        Returns:
            int: 成功标记的文章数量
        """
        if not article_ids:
            return 0

        async with db.get_session() as session:
            # 使用 UPDATE ... WHERE id IN (...) 一次性更新
            now = datetime.now(timezone.utc)
            stmt = (
                update(Article)
                .where(Article.id.in_(article_ids))
                .values(
                    is_pushed=True,
                    pushed_at=now,
                    status=ArticleStatus.PUBLISHED.value
                )
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(OperationalError),
        reraise=True,
    )
    async def _batch_update_impl(self, results: List[dict]) -> int:
        """
        带重试的批量更新实现（Phase P0-C）

        仅重试 OperationalError（database locked、busy）
        """
        updated_count = 0
        async with db.get_session() as session:
            for item in results:
                url_hash = item["url_hash"]
                content = item["content"]

                if not content or len(content) < 100:
                    continue

                stmt = select(Article).where(Article.url_hash == url_hash)
                result = await session.execute(stmt)
                article = result.scalar_one_or_none()

                if article:
                    article.content = content
                    updated_count += 1

            await session.commit()
        return updated_count

    async def batch_update_article_contents(self, results: List[dict]) -> int:
        """
        批量更新文章 content 字段

        Phase P0-B (B1方案)：在一个事务中批量 UPDATE，避免 N 个独立事务
        Phase P0-C：添加 tenacity 重试，避免 OperationalError 导致全部更新丢失

        Args:
            results: [{"url_hash": "abc", "content": "full text"}, ...]

        Returns:
            int: 成功更新的文章数
        """
        if not results:
            return 0

        try:
            updated_count = await self._batch_update_impl(results)
            logger.info(f"批量更新完成: {updated_count}/{len(results)} 篇")
            return updated_count
        except Exception as e:
            logger.error(f"批量更新失败（已重试 3 次）: {e}")
            return 0


# 创建全局实例
deduplicator = Deduplicator()
