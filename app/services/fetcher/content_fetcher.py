# -*- coding: utf-8 -*-
"""
内容提取模块

使用 Trafilatura 从网页提取完整正文，用于补充 RSS 源中缺失的 content 字段。
"""

import asyncio
import logging
from typing import Optional

import trafilatura

logger = logging.getLogger(__name__)


class TrafilaturaContentFetcher:
    """
    使用 Trafilatura 从网页提取完整正文

    用于补充 RSS 源中缺失的 content 字段
    """

    TIMEOUT = 15  # 提取超时（秒）
    # MIN_LENGTH 已移至 config.py（Phase P1-A），长度判断由调用方执行

    async def fetch_content(self, url: str) -> Optional[str]:
        """
        从给定 URL 提取正文

        最小长度判断由调用方执行（Phase P1-A 配置化）

        Args:
            url: 网页 URL

        Returns:
            提取的正文文本（Markdown 格式），失败返回 None
        """
        try:
            # 使用 asyncio.to_thread 包装同步调用
            content = await asyncio.to_thread(self._extract, url)

            if content:
                logger.info(f"Trafilatura 提取成功: {url} ({len(content)} 字符)")
                return content

            logger.debug(f"Trafilatura 提取内容为空: {url}")
            return None

        except Exception as e:
            logger.warning(f"Trafilatura 提取失败: {url}, 错误: {e}")
            return None

    def _extract(self, url: str) -> Optional[str]:
        """
        使用 Trafilatura 提取正文（同步）

        Args:
            url: 网页 URL

        Returns:
            提取的正文文本
        """
        try:
            # trafilatura.fetch_url 是同步函数
            downloaded = trafilatura.fetch_url(url)

            if not downloaded:
                logger.debug(f"Trafilatura 无法获取页面: {url}")
                return None

            # trafilatura.extract 是同步函数
            # output_format="markdown" 返回 Markdown 格式
            text = trafilatura.extract(
                downloaded,
                output_format="markdown",
                include_comments=False,
                include_tables=True,
                include_images=False,
                include_links=True,
            )

            return text

        except Exception as e:
            logger.error(f"Trafilatura 内部错误: {url}, 错误: {e}")
            return None

    async def batch_fetch(
        self, urls: list[str], concurrency: int = 3
    ) -> dict[str, Optional[str]]:
        """
        批量提取正文

        Args:
            urls: URL 列表
            concurrency: 并发数

        Returns:
            {url: content} 字典，失败的 url 值为 None
        """
        semaphore = asyncio.Semaphore(concurrency)
        results = {}

        async def _fetch_with_limit(url: str):
            async with semaphore:
                content = await self.fetch_content(url)
                results[url] = content

        # 并发执行
        tasks = [_fetch_with_limit(url) for url in urls]
        await asyncio.gather(*tasks, return_exceptions=True)

        success_count = sum(1 for v in results.values() if v is not None)
        logger.info(
            f"批量提取完成: {len(urls)} 个 URL, {success_count} 个成功"
        )

        return results


# 创建全局实例
content_fetcher = TrafilaturaContentFetcher()
