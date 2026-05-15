# -*- coding: utf-8 -*-
"""
向量服务核心编排层

7 个业务场景的统一入口：
- S1: 语义去重（deduplicate）
- S2: LLM 缓存（check_llm_cache / record_cache_hit）
- S3: 语义搜索（search）
- S4: Agent RAG（retrieve_for_agent）
- S5: 相似推荐（recommend）
- S6: 主题聚类（cluster）
- S7: GitHub 相似（find_similar_repos）

设计原则：
- 所有方法为 async，向量库/Embedding 不可用时优雅降级
- 数据库查询与向量查询分离（先向量检索，再 SQLite 补充字段）
- 向量相似度统一为 0.0~1.0（1.0 = 完全相同）
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from app.config import get_settings
from app.database import db
from app.models import Article, ArticleStatus
from sqlalchemy import select, update

from .embedding_manager import embedding_manager
from .exceptions import (
    AllEmbeddingModelsUnavailableError,
    EmbeddingError,
    VectorDBNotAvailableError,
)
from .schemas import (
    CacheResult,
    ClusterResult,
    DedupResult,
    RAGContext,
    RecommendResult,
    SearchFilters,
    SearchResult,
)
from .vector_db_manager import vector_db_manager

logger = logging.getLogger(__name__)

RECOMMEND_SIMILARITY_THRESHOLD = 0.80


class VectorService:
    """
    向量服务核心编排

    封装 7 个业务场景的向量检索逻辑。
    """

    def _build_embedding_text(
        self,
        title: str,
        content: str = "",
        summary: str = "",
    ) -> str:
        """
        构建 embedding 用的文本

        策略：
        1. 优先使用 title + content
        2. 如果 title + content 超长：
           - 如果 summary 可用，降级为 title + summary
           - 如果 summary 不可用，截断 title + content
        3. 如果 content 不可用，使用 title

        注意：summary 在文章处理早期阶段可能为空（LLM 尚未处理）
        """
        settings = get_settings()
        max_len = settings.embedding_max_text_length

        if content:
            full_text = f"{title}\n{content}"
        else:
            full_text = title

        if len(full_text) > max_len:
            if summary:
                # summary 可用，降级为 title + summary
                logger.debug(
                    "Embedding 文本降级: title + summary "
                    "(原始长度 %d > 阈值 %d)",
                    len(full_text),
                    max_len,
                )
                full_text = f"{title}\n{summary}"
            else:
                # summary 不可用，直接截断 title + content
                # 保留 max_len 字符，避免信息过度丢失
                logger.debug(
                    "Embedding 文本截断: title + content[:%d] "
                    "(原始长度 %d > 阈值 %d, summary 不可用)",
                    max_len,
                    len(full_text),
                    max_len,
                )
                full_text = full_text[:max_len]

        return full_text[:max_len]

    # ===== S1: 语义去重 =====
    async def deduplicate(
        self,
        title: str,
        content: str = "",
        summary: str = "",
        rss_source_id: Optional[int] = None,
    ) -> DedupResult:
        """
        语义去重检测

        策略：
        - 向量库不可用 → 降级放行（is_duplicate=False）
        - 同一 RSS 源内不做去重（避免系列文章误判）
        - 相似度 ≥ dedup_similarity_threshold（默认 0.88）视为重复

        Args:
            title: 文章标题
            content: 文章正文
            summary: 文章摘要
            rss_source_id: RSS 源 ID，同一源内不做去重

        Returns:
            DedupResult
        """
        if not vector_db_manager.is_available() or not embedding_manager.is_available():
            return DedupResult(is_duplicate=False)

        try:
            settings = get_settings()
            text = self._build_embedding_text(title, content, summary)
            embeddings = await embedding_manager.embed([text])
            if not embeddings:
                return DedupResult(is_duplicate=False)

            filter_conditions: dict[str, Any] | None = None
            if rss_source_id is not None:
                filter_conditions = {
                    "source_type": {"$ne": f"rss_{rss_source_id}"}
                }

            adapter = await vector_db_manager.get_adapter()
            results = await adapter.query(
                collection=vector_db_manager.get_collection_name("articles"),
                query_embedding=embeddings[0],
                top_k=settings.semantic_search_top_k,
                filter_conditions=filter_conditions,
            )

            threshold = settings.dedup_similarity_threshold
            for r in results:
                if r["score"] >= threshold:
                    matched_id = r["metadata"].get("article_id")
                    logger.info(
                        "语义去重命中: article_id=%s, similarity=%.3f, threshold=%.2f",
                        matched_id,
                        r["score"],
                        threshold,
                    )
                    return DedupResult(
                        is_duplicate=True,
                        matched_article_id=matched_id,
                        similarity_score=r["score"],
                    )

            return DedupResult(is_duplicate=False)

        except VectorDBNotAvailableError:
            logger.debug("向量库不可用，去重降级放行")
            return DedupResult(is_duplicate=False)
        except (EmbeddingError, AllEmbeddingModelsUnavailableError):
            logger.debug("Embedding 服务不可用，去重降级放行")
            return DedupResult(is_duplicate=False)
        except Exception as e:
            logger.warning("语义去重异常（降级放行）: %s", e)
            return DedupResult(is_duplicate=False)

    # ===== S2: LLM 处理缓存 =====
    async def check_llm_cache(
        self,
        title: str,
        content: str = "",
        summary: str = "",
        ttl_days: int = 1,
    ) -> CacheResult:
        """
        查询 LLM 处理缓存

        逻辑：
        1. 用 title+content 生成 embedding
        2. 向量库检索相似文章
        3. 找到相似度 ≥ 0.85 的已处理文章
        4. 返回其 summary/keywords/tags/score/score_reason

        注意：缓存仅复用 summary/keywords/tags/score/score_reason，不复用 content

        Args:
            title: 文章标题
            content: 文章正文
            summary: 文章摘要
            ttl_days: 缓存有效期（天）

        Returns:
            CacheResult
        """
        if not vector_db_manager.is_available() or not embedding_manager.is_available():
            return CacheResult(is_hit=False)

        try:
            settings = get_settings()
            text = self._build_embedding_text(title, content, summary)
            embeddings = await embedding_manager.embed([text])
            if not embeddings:
                return CacheResult(is_hit=False)

            adapter = await vector_db_manager.get_adapter()
            results = await adapter.query(
                collection=vector_db_manager.get_collection_name("articles"),
                query_embedding=embeddings[0],
                top_k=settings.semantic_cache_top_k,
            )

            for r in results:
                if r["score"] < settings.cache_similarity_threshold:
                    continue

                matched_id = r["metadata"].get("article_id")
                if matched_id is None:
                    continue

                async with db.get_session() as session:
                    result = await session.execute(
                        select(Article).where(
                            Article.id == matched_id,
                            Article.status == ArticleStatus.PROCESSED.value,
                        )
                    )
                    source_article = result.scalar_one_or_none()

                if source_article is None:
                    continue

                logger.info(
                    "LLM 缓存命中: source=%s, similarity=%.3f",
                    matched_id,
                    r["score"],
                )
                return CacheResult(
                    is_hit=True,
                    cached_article_id=matched_id,
                    similarity_score=r["score"],
                    cached_data={
                        "summary": source_article.summary,
                        "keywords": source_article.keywords,
                        "tags": source_article.tags,
                        "score": source_article.score,
                        "score_reason": getattr(source_article, "score_reason", None) or "",
                    },
                )

            return CacheResult(is_hit=False)

        except VectorDBNotAvailableError:
            logger.debug("向量库不可用，缓存查询降级未命中")
            return CacheResult(is_hit=False)
        except (EmbeddingError, AllEmbeddingModelsUnavailableError):
            logger.debug("Embedding 服务不可用，缓存查询降级未命中")
            return CacheResult(is_hit=False)
        except Exception as e:
            logger.warning("LLM 缓存查询异常（降级未命中）: %s", e)
            return CacheResult(is_hit=False)

    async def record_cache_hit(
        self,
        source_article_id: int,
        cached_article_id: int,
        similarity_score: float,
        ttl_days: int = 1,
    ) -> None:
        """
        记录缓存命中到 SQLite

        Args:
            source_article_id: 当前文章 ID（将复用缓存）
            cached_article_id: 被复用的源文章 ID
            similarity_score: 相似度
            ttl_days: 缓存有效期（天）
        """
        try:
            from app.models import LLMCacheEntry

            async with db.get_session() as session:
                entry = LLMCacheEntry(
                    source_article_id=source_article_id,
                    cached_article_id=cached_article_id,
                    similarity_score=similarity_score,
                    cache_ttl_days=ttl_days,
                )
                session.add(entry)
                await session.commit()
                logger.debug(
                    "缓存命中记录已写入: source=%d, cached=%d",
                    source_article_id,
                    cached_article_id,
                )
        except Exception as e:
            logger.warning("缓存记录写入失败: %s", e)

    # ===== S3/S4: 语义搜索 + Agent RAG =====
    async def search(
        self,
        query: str,
        top_k: int = 20,
        filters: Optional[SearchFilters] = None,
        sort_weights: tuple[float, float] = (0.7, 0.3),
    ) -> list[SearchResult]:
        """
        语义搜索

        策略：
        - 向量检索 top_k*2，过量召回后精排
        - 混合排序：similarity × 0.7 + (score/100) × 0.3
        - 从 SQLite 补充完整文章信息

        Args:
            query: 自然语言搜索词
            top_k: 返回数量
            filters: 过滤条件
            sort_weights: (相似度权重, 评分权重)

        Returns:
            SearchResult 列表
        """
        if not vector_db_manager.is_available() or not embedding_manager.is_available():
            return []

        try:
            embeddings = await embedding_manager.embed([query])
            if not embeddings:
                return []

            adapter = await vector_db_manager.get_adapter()
            results = await adapter.query(
                collection=vector_db_manager.get_collection_name("articles"),
                query_embedding=embeddings[0],
                top_k=top_k * 2,
            )

            scored: list[tuple[float, dict]] = []
            for r in results:
                article_id = r["metadata"].get("article_id")
                article_score = r["metadata"].get("score") or 0
                mixed = r["score"] * sort_weights[0] + (article_score / 100.0) * sort_weights[1]
                scored.append((mixed, r, article_id))

            scored.sort(key=lambda x: x[0], reverse=True)

            # 收集所有 article_id 进行批量查询（避免 N+1 查询）
            article_ids = []
            for _, r, article_id in scored:
                if article_id is not None:
                    article_ids.append(article_id)

            # 批量查询文章
            articles_map: dict[int, Article] = {}
            if article_ids:
                async with db.get_session() as session:
                    result = await session.execute(
                        select(Article).where(Article.id.in_(article_ids))
                    )
                    articles_map = {a.id: a for a in result.scalars().all()}

            # 构建搜索结果
            search_results: list[SearchResult] = []
            seen_ids: set[int] = set()

            for mixed_score, r, article_id in scored:
                if article_id is None:
                    continue
                if article_id in seen_ids:
                    continue
                seen_ids.add(article_id)

                article = articles_map.get(article_id)
                if article is None:
                    continue

                if filters:
                    if not self._article_matches_filters(article, filters):
                        continue

                search_results.append(SearchResult(
                    article_id=article.id,
                    title=article.title or "",
                    summary=article.summary,
                    similarity=r["score"],
                    score=article.score,
                    published_at=article.published_at,
                    url=article.url,
                    source_name=article.source_name,
                ))

                if len(search_results) >= top_k:
                    break

            return search_results

        except Exception as e:
            logger.warning("语义搜索异常: %s", e)
            return []

    def _article_matches_filters(self, article: Article, filters: SearchFilters) -> bool:
        """检查文章是否满足过滤条件"""
        if filters.score_min is not None:
            if (article.score or 0) < filters.score_min:
                return False
        if filters.score_max is not None:
            if (article.score or 0) > filters.score_max:
                return False
        if filters.date_from is not None:
            if article.published_at and article.published_at < filters.date_from:
                return False
        if filters.date_to is not None:
            if article.published_at and article.published_at > filters.date_to:
                return False
        if filters.status is not None:
            if article.status != filters.status:
                return False
        if filters.source_type is not None:
            if article.source_name != filters.source_type:
                return False
        return True

    async def retrieve_for_agent(
        self,
        question: str,
        top_k: int = 10,
        score_min: int = 60,
    ) -> list[RAGContext]:
        """
        Agent RAG 上下文检索

        从向量库检索相关文章，构造 LLM 对话上下文。
        摘要截断至约 400 字符（约 200 tokens）

        Args:
            question: 用户/Agent 的自然语言问题
            top_k: 返回上下文片段数量
            score_min: 只返回评分 ≥ score_min 的文章

        Returns:
            RAGContext 列表
        """
        if not vector_db_manager.is_available() or not embedding_manager.is_available():
            return []

        try:
            embeddings = await embedding_manager.embed([question])
            if not embeddings:
                return []

            adapter = await vector_db_manager.get_adapter()
            results = await adapter.query(
                collection=vector_db_manager.get_collection_name("articles"),
                query_embedding=embeddings[0],
                top_k=top_k,
            )

            # 收集所有 article_id 进行批量查询（避免 N+1 查询）
            article_ids = []
            for r in results:
                article_id = r["metadata"].get("article_id")
                if article_id is not None:
                    article_ids.append(article_id)

            # 批量查询文章（带过滤条件）
            articles_map: dict[int, Article] = {}
            if article_ids:
                async with db.get_session() as session:
                    result = await session.execute(
                        select(Article).where(
                            Article.id.in_(article_ids),
                            Article.status == ArticleStatus.PROCESSED.value,
                            Article.score >= score_min,
                        )
                    )
                    articles_map = {a.id: a for a in result.scalars().all()}

            # 构建 RAG 上下文
            contexts: list[RAGContext] = []
            for r in results:
                article_id = r["metadata"].get("article_id")
                if article_id is None:
                    continue

                article = articles_map.get(article_id)
                if article is None:
                    continue

                summary = article.summary or ""
                if len(summary) > 400:
                    summary = summary[:397] + "..."

                contexts.append(RAGContext(
                    article_id=article.id,
                    title=article.title or "",
                    summary=summary,
                    similarity=r["score"],
                    published_at=article.published_at,
                    url=article.url,
                ))

            return contexts

        except Exception as e:
            logger.warning("Agent RAG 检索异常: %s", e)
            return []

    # ===== S5: 相似文章推荐 =====
    async def recommend(
        self,
        article_id: int,
        top_k: int = 5,
        status_filter: str = "processed",
    ) -> list[RecommendResult]:
        """
        相似文章推荐

        基于当前文章的向量，在向量库中检索最相似的文章。
        用于文章详情页「相关阅读」场景。

        Args:
            article_id: 当前文章 ID
            top_k: 返回推荐数量
            status_filter: 文章状态过滤，默认只返回 processed 文章

        Returns:
            RecommendResult 列表
        """
        if not vector_db_manager.is_available() or not embedding_manager.is_available():
            return []

        try:
            adapter = await vector_db_manager.get_adapter()
            records = await adapter.get(vector_db_manager.get_collection_name("articles"), [str(article_id)])
            if not records or not records[0].get("embedding"):
                return []

            embedding = records[0]["embedding"]
            # 多取一些结果，后续会过滤掉自身和非目标状态文章
            results = await adapter.query(
                collection=vector_db_manager.get_collection_name("articles"),
                query_embedding=embedding,
                top_k=top_k + 20,
            )

            # 第一层过滤：排除自身 + 相似度阈值
            candidates: list[tuple[int, dict]] = []
            seen: set[str] = {str(article_id)}

            for r in results:
                rid = r["id"]
                if rid in seen:
                    continue
                seen.add(rid)

                if r["score"] < RECOMMEND_SIMILARITY_THRESHOLD:
                    continue

                aid = r["metadata"].get("article_id")
                if aid is None:
                    continue

                try:
                    candidates.append((int(aid), r))
                except (ValueError, TypeError):
                    continue

            if not candidates:
                return []

            # 第二层过滤：查询 SQLite 验证文章状态
            candidate_ids = [aid for aid, _ in candidates]
            async with db.get_session() as session:
                result = await session.execute(
                    select(Article.id).where(
                        Article.id.in_(candidate_ids),
                        Article.status == status_filter,
                    )
                )
                valid_ids = {row[0] for row in result.all()}

            # 构建最终结果（保持相似度排序）
            recommends: list[RecommendResult] = []
            for aid, r in candidates:
                if aid not in valid_ids:
                    continue

                recommends.append(RecommendResult(
                    article_id=aid,
                    title=r["metadata"].get("title") or "",
                    similarity=r["score"],
                    score=r["metadata"].get("score"),
                ))

                if len(recommends) >= top_k:
                    break

            logger.debug(
                "相似推荐: article_id=%d, candidates=%d, valid=%d, returned=%d",
                article_id, len(candidates), len(valid_ids), len(recommends)
            )
            return recommends

        except Exception as e:
            logger.warning("相似推荐异常: article_id=%d, error=%s", article_id, e)
            return []

    # ===== S7: GitHub 仓库相似度 =====

    async def find_similar_repos(
        self,
        repo_id: int,
        top_k: int = 5,
    ) -> list[dict]:
        """
        GitHub 仓库相似度检索

        在 github_repos 集合中检索与指定仓库最相似的其他仓库。
        用于 GitHub trending 分析和仓库推荐。

        Args:
            repo_id: 目标仓库 ID
            top_k: 返回数量

        Returns:
            [{"repo_id", "full_name", "similarity", "language", "stars"}, ...]
        """
        if not vector_db_manager.is_available() or not embedding_manager.is_available():
            return []

        try:
            adapter = await vector_db_manager.get_adapter()
            records = await adapter.get(vector_db_manager.get_collection_name("github_repos"), [str(repo_id)])
            if not records or not records[0].get("embedding"):
                return []

            embedding = records[0]["embedding"]
            results = await adapter.query(
                collection=vector_db_manager.get_collection_name("github_repos"),
                query_embedding=embedding,
                top_k=top_k + 1,
            )

            similar: list[dict] = []
            for r in results:
                if r["id"] == str(repo_id):
                    continue
                if r["score"] < RECOMMEND_SIMILARITY_THRESHOLD:
                    continue

                similar.append({
                    "repo_id": r["metadata"].get("repo_id"),
                    "full_name": r["metadata"].get("full_name") or "",
                    "similarity": r["score"],
                    "language": r["metadata"].get("language") or "",
                    "stars": r["metadata"].get("stars") or 0,
                })

                if len(similar) >= top_k:
                    break

            return similar

        except Exception as e:
            logger.warning("GitHub 相似度检索异常: %s", e)
            return []

    # ===== S6: 主题聚类 =====
    async def cluster(
        self,
        days: int = 7,
        min_cluster_size: int = 3,
    ) -> list[ClusterResult]:
        """
        主题聚类与热点发现

        使用 HDBSCAN 对最近 N 天的已处理文章进行向量聚类，
        提取关键词、计算热度、持久化到数据库。

        Args:
            days: 分析最近 N 天的文章
            min_cluster_size: HDBSCAN 最小簇大小

        Returns:
            ClusterResult 列表（按 hotness 降序）
        """
        if not vector_db_manager.is_available() or not embedding_manager.is_available():
            return []

        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)

            async with db.get_session() as session:
                result = await session.execute(
                    select(Article).where(
                        Article.status == ArticleStatus.PROCESSED.value,
                        Article.created_at >= cutoff,
                        Article.has_vector == True,
                    )
                )
                articles = result.scalars().all()

            if len(articles) < min_cluster_size:
                logger.info("聚类跳过：仅 %d 篇文章，不足 %d", len(articles), min_cluster_size)
                return []

            article_ids = [a.id for a in articles]
            adapter = await vector_db_manager.get_adapter()
            records = await adapter.get(vector_db_manager.get_collection_name("articles"), [str(aid) for aid in article_ids])

            embeddings: list[list[float]] = []
            valid_articles: list[Article] = []
            for i, r in enumerate(records):
                if r.get("embedding") is not None:
                    embeddings.append(r["embedding"])
                    valid_articles.append(articles[i])

            if len(valid_articles) < min_cluster_size:
                return []

            import numpy as np
            embeddings_array = np.array(embeddings)

            import hdbscan
            clusterer = hdbscan.HDBSCAN(
                min_cluster_size=min_cluster_size,
                metric="euclidean",
            )
            labels = clusterer.fit_predict(embeddings_array)

            unique_labels = set(labels)
            clusters: list[ClusterResult] = []

            for label in unique_labels:
                if label == -1:
                    continue

                indices = [i for i, l in enumerate(labels) if l == label]
                cluster_articles = [valid_articles[i] for i in indices]

                all_text = " ".join(
                    f"{a.title} {a.summary or ''}" for a in cluster_articles
                )
                keywords = self._extract_keywords(all_text, top_n=5)

                scores = [a.score or 0 for a in cluster_articles]
                avg_score = float(np.mean(scores))
                hotness = len(cluster_articles) * (avg_score / 100.0)

                clusters.append(ClusterResult(
                    cluster_id=0,
                    keywords=keywords,
                    article_count=len(cluster_articles),
                    avg_score=round(avg_score, 1),
                    hotness=round(hotness, 2),
                    is_emerging=await self._is_emerging_topic(keywords),
                    representative_ids=[a.id for a in cluster_articles[:5]],
                ))

            clusters.sort(key=lambda c: c.hotness, reverse=True)

            await self._persist_clusters(clusters)

            return clusters

        except Exception as e:
            logger.error("主题聚类异常: %s", e, exc_info=True)
            return []

    def _extract_keywords(self, text: str, top_n: int = 5) -> list[str]:
        """简易 TF-IDF 关键词提取（基于词频）"""
        import re
        from collections import Counter

        # 匹配英文单词、中文字符序列（不拆分中文词组）
        words = re.findall(r"[a-zA-Z]+|[\u4e00-\u9fff]+", text.lower())
        filtered = [w for w in words if len(w) >= 2 and not w.isdigit()]
        counter = Counter(filtered)
        return [word for word, _ in counter.most_common(top_n)]

    async def _is_emerging_topic(self, keywords: list[str]) -> bool:
        """判断是否为新兴话题（简化：与上一周期聚类比较）"""
        try:
            from app.models import ClusterTopic
            cutoff = datetime.now(timezone.utc) - timedelta(days=14)
            async with db.get_session() as session:
                result = await session.execute(
                    select(ClusterTopic).where(
                        ClusterTopic.cluster_date >= cutoff,
                    ).order_by(ClusterTopic.cluster_date.desc()).limit(10)
                )
                recent_topics = result.scalars().all()

            if not recent_topics:
                return True

            for topic in recent_topics:
                prev_keywords = json.loads(topic.keywords) if topic.keywords else []
                overlap = len(set(keywords) & set(prev_keywords))
                if overlap >= 2:
                    return False
            return True
        except Exception:
            return True

    async def _persist_clusters(self, clusters: list[ClusterResult]) -> None:
        """持久化聚类结果到 SQLite"""
        from app.models import ClusterTopic, ClusterArticle

        async with db.get_session() as session:
            for c in clusters:
                topic = ClusterTopic(
                    cluster_date=datetime.now(timezone.utc),
                    keywords=json.dumps(c.keywords),
                    article_count=c.article_count,
                    avg_score=c.avg_score,
                    hotness=c.hotness,
                    is_emerging=c.is_emerging,
                    representative_article_ids=json.dumps(c.representative_ids),
                )
                session.add(topic)
                await session.flush()

                for aid in c.representative_ids:
                    ca = ClusterArticle(cluster_id=topic.id, article_id=aid)
                    session.add(ca)

            await session.commit()
        logger.info("持久化 %d 个聚类主题", len(clusters))


vector_service = VectorService()