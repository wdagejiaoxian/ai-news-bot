# -*- coding: utf-8 -*-
"""
文章向量索引器

维护 SQLite（Article.has_vector）和向量库（ChromaDB）的最终一致性。
采用异步队列写入模式，避免阻塞主流程。

设计要点：
- 生产者：index_article() 将文章投递到队列（fire-and-forget）
- 消费者：后台协程池从队列取任务执行索引写入
- 对账：reindex_stale() 每天凌晨运行，补索引 has_vector=False 的已处理文章
- 队列满时丢弃最旧任务，避免内存无限增长
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select, update

from app.config import get_settings
from app.database import db
from app.models import Article, ArticleStatus
from .embedding_manager import embedding_manager
from .exceptions import VectorDBNotAvailableError, EmbeddingError, AllEmbeddingModelsUnavailableError
from .vector_db_manager import vector_db_manager

logger = logging.getLogger(__name__)


class ArticleIndexer:
    """
    文章向量索引器（最终一致性异步写入）

    工作流程：
    1. 外部调用 index_article() 将文章投递到内存队列
    2. 后台消费者协程池批量从队列取任务
    3. 每个任务：生成 embedding → 写入向量库 → 更新 Article.has_vector=True
    4. 对账任务：每天凌晨检查 has_vector=False 的已处理文章，补投队列
    """

    def __init__(self, queue_maxsize: int = 1000):
        self._queue: asyncio.Queue[tuple[int, str, dict]] = asyncio.Queue(maxsize=queue_maxsize)
        self._consumer_tasks: list[asyncio.Task] = []
        self._running = False
        self._start_lock = asyncio.Lock()

    async def start(self, concurrency: int = 3) -> None:
        """
        启动后台消费者协程池

        Args:
            concurrency: 并发消费者数量
        """
        async with self._start_lock:
            if self._running:
                logger.warning("ArticleIndexer 已在运行，忽略重复启动")
                return
            self._running = True
            for i in range(concurrency):
                task = asyncio.create_task(self._consume_loop(), name=f"article-indexer-{i}")
                self._consumer_tasks.append(task)
            logger.info("ArticleIndexer 启动，%d 个消费者", concurrency)

    async def _consume_loop(self) -> None:
        """消费者循环：从队列取任务并执行"""
        while self._running:
            try:
                article_id, text, metadata = await asyncio.wait_for(
                    self._queue.get(), timeout=5.0
                )
                try:
                    await self._index_single(article_id, text, metadata)
                finally:
                    self._queue.task_done()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("文章索引消费者异常: %s", e)

    def _build_embedding_text(self, article_data: dict[str, Any]) -> str:
        """
        构建 embedding 用的文本

        策略：
        1. 优先使用 title + content
        2. 如果 title + content 超长：
           - 如果 summary 可用，降级为 title + summary
           - 如果 summary 不可用，截断 title + content
        3. 如果 content 不可用，使用 title

        注意：summary 在文章处理早期阶段可能为空（LLM 尚未处理）

        Args:
            article_data: 包含 title/content/summary 的字典

        Returns:
            用于生成 embedding 的文本
        """
        settings = get_settings()
        max_len = settings.embedding_max_text_length

        title = article_data.get("title") or ""
        content = article_data.get("content") or ""
        summary = article_data.get("summary") or ""

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

    async def index_article(self, article_id: int, article_data: dict[str, Any]) -> bool:
        """
        将文章投递到索引队列（非阻塞）

        Args:
            article_id: 文章 ID
            article_data: 包含 title/content/summary/source_type/processed_at/score 的字典

        Returns:
            True = 投递成功，False = 队列满或向量库不可用
        """
        if not vector_db_manager.is_available() or not embedding_manager.is_available():
            return False

        text = self._build_embedding_text(article_data)
        processed_at = article_data.get("processed_at")
        if isinstance(processed_at, datetime):
            processed_at_iso = processed_at.isoformat()
        elif processed_at:
            processed_at_iso = str(processed_at)
        else:
            processed_at_iso = None

        metadata = {
            "article_id": article_id,
            "source_type": article_data.get("source_type", ""),
            "processed_at": processed_at_iso,
            "score": article_data.get("score") or 0,
        }

        try:
            self._queue.put_nowait((article_id, text, metadata))
            return True
        except asyncio.QueueFull:
            logger.warning("索引队列已满，丢弃最旧任务后重试")
            try:
                self._queue.get_nowait()
                self._queue.put_nowait((article_id, text, metadata))
                return True
            except Exception:
                return False

    async def _index_single(
        self, article_id: int, text: str, metadata: dict[str, Any]
    ) -> None:
        """
        单条写入向量库（含重试）

        Args:
            article_id: 文章 ID
            text: embedding 文本
            metadata: 向量元数据
        """
        max_retries = get_settings().embedding_max_retries
        last_error: Exception | None = None

        for attempt in range(max_retries):
            try:
                embeddings = await embedding_manager.embed([text])
                if not embeddings:
                    logger.warning("文章 %d embedding 为空，跳过索引", article_id)
                    return

                adapter = await vector_db_manager.get_adapter()
                await adapter.add(
                    collection=vector_db_manager.get_collection_name("articles"),
                    ids=[str(article_id)],
                    embeddings=embeddings,
                    metadatas=[metadata],
                    documents=[text],
                )

                async with db.get_session() as session:
                    await session.execute(
                        update(Article)
                        .where(Article.id == article_id)
                        .values(has_vector=True)
                    )
                    await session.commit()

                logger.debug("文章 %d 向量索引成功", article_id)
                return

            except VectorDBNotAvailableError:
                logger.debug("向量库不可用，文章 %d 将在恢复后对账", article_id)
                return
            except (EmbeddingError, AllEmbeddingModelsUnavailableError) as e:
                logger.warning("文章 %d embedding 失败（尝试 %d/%d）: %s", article_id, attempt + 1, max_retries, e)
                last_error = e
            except Exception as e:
                logger.warning("文章 %d 索引失败（尝试 %d/%d）: %s", article_id, attempt + 1, max_retries, e)
                last_error = e

            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)

        logger.error("文章 %d 索引写入失败（已重试 %d 次）: %s", article_id, max_retries, last_error)

    async def deindex_article(self, article_id: int) -> None:
        """
        从向量库删除单条向量

        Args:
            article_id: 文章 ID
        """
        try:
            adapter = await vector_db_manager.get_adapter()
            await adapter.delete(vector_db_manager.get_collection_name("articles"), [str(article_id)])

            async with db.get_session() as session:
                await session.execute(
                    update(Article)
                    .where(Article.id == article_id)
                    .values(has_vector=False)
                )
                await session.commit()

            logger.info("文章 %d 向量已删除", article_id)
        except VectorDBNotAvailableError:
            logger.warning("向量库不可用，文章 %d 向量删除操作跳过", article_id)
        except Exception as e:
            logger.warning("删除文章 %d 向量失败: %s", article_id, e)

    async def reindex_stale(self, max_age_hours: int = 24, batch_size: int = 500) -> int:
        """
        对账：补索引 has_vector=False 的已处理文章

        每天凌晨由定时任务调用，发现向量库中缺失的文章并重新索引。

        Args:
            max_age_hours: 只处理最近 N 小时内更新的文章（避免扫描全表）
            batch_size: 每批处理数量

        Returns:
            投递到队列的文章数量
        """
        from datetime import timedelta

        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)

        async with db.get_session() as session:
            result = await session.execute(
                select(Article)
                .where(
                    Article.has_vector == False,
                    Article.status == ArticleStatus.PROCESSED.value,
                    Article.updated_at >= cutoff_time,
                )
                .limit(batch_size)
            )
            stale_articles = result.scalars().all()

        if not stale_articles:
            logger.info("对账：无需补索引")
            return 0

        logger.info("对账：发现 %d 篇缺少向量的文章，开始补索引", len(stale_articles))
        count = 0

        for article in stale_articles:
            data = {
                "title": article.title,
                "content": article.content,
                "summary": article.summary,
                "source_type": f"rss_{article.source_name}" if article.source_name else "rss",
                "processed_at": article.updated_at,
                "score": article.score,
            }
            if await self.index_article(article.id, data):
                count += 1

        logger.info("对账：已将 %d/%d 篇文章投递到索引队列", count, len(stale_articles))
        return count

    async def shutdown(self, timeout: float = 10.0) -> None:
        """
        优雅关闭：停止消费，清空队列

        Args:
            timeout: 等待消费者完成当前任务的最大秒数
        """
        logger.info("ArticleIndexer 关闭中...")
        self._running = False

        for task in self._consumer_tasks:
            task.cancel()

        if self._consumer_tasks:
            await asyncio.wait_for(
                asyncio.gather(*self._consumer_tasks, return_exceptions=True),
                timeout=timeout,
            )

        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except asyncio.QueueEmpty:
                break

        self._consumer_tasks.clear()
        self._running = False
        logger.info("ArticleIndexer 已关闭")


article_indexer = ArticleIndexer()