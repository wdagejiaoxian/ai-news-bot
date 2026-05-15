# -*- coding: utf-8 -*-
"""
RSS 解析和数据采集模块

负责从 RSS 订阅源获取AI资讯
支持多种RSS格式和网站
"""

import asyncio
import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import feedparser
import httpx
from bs4 import BeautifulSoup

# Phase 4 N3 优化: 预编译 regex 常量，避免每次调用重新编译
_URL_PATTERN = re.compile(r"https?://\S+")
_WHITESPACE_PATTERN = re.compile(r"\s+")

# Phase 1 PH1 优化: 单篇文章补全独立超时（秒）
# 目的：避免单篇文章下载阻塞整体采集流程
# 设计：国内网站通常 3-5s 内响应，GFW 阻挡的 URL 直接 timeout
PER_ARTICLE_ENRICH_TIMEOUT = 8

logger = logging.getLogger(__name__)


class RSSFetcher:
    """
    RSS 订阅源采集器

    功能:
    - 解析 RSS/Atom 订阅源
    - 获取文章内容和元数据
    - 支持自定义网站爬虫

    常见RSS源:
    - OpenAI Blog: https://openai.com/blog/rss.xml
    - TechCrunch: https://techcrunch.com/feed/
    - Hacker News: https://news.ycombinator.com/rss
    - 36Kr: https://36kr.com/feed/
    """

    # Phase 3 N1 优化: 类级延迟导入缓存
    _content_fetcher_instance = None

    # Phase 2 PH2 优化: 域名跳过缓存
    _skip_domains_set = None

    # Phase 3A 修正: 同步补全模式缓存
    _immediate_enrichment_enabled = None

    @classmethod
    def _get_skip_domains(cls) -> set:
        """
        获取跳过补全的域名集合（带缓存）

        Phase 2 PH2 优化：避免每次补全都解析配置
        """
        if cls._skip_domains_set is None:
            from app.config import get_settings
            domains_str = get_settings().trafilatura_skip_domains
            cls._skip_domains_set = set(
                d.strip().lower() for d in domains_str.split("|")
                if d.strip()
            )
        return cls._skip_domains_set

    @classmethod
    def _is_immediate_enrichment_enabled(cls) -> bool:
        """
        检查是否启用采集阶段同步补全

        Phase 3A 修正：采集阶段默认关闭同步补全，改为后台异步补全
        仅紧急情况或测试时启用
        """
        if cls._immediate_enrichment_enabled is None:
            from app.config import get_settings
            cls._immediate_enrichment_enabled = (
                get_settings().trafilatura_enable_immediate_enrichment
            )
        return cls._immediate_enrichment_enabled

    @classmethod
    def _should_skip_enrichment(cls, url: str) -> bool:
        """
        检查 URL 是否应跳过补全

        Phase P1-D 优化：统一使用动态跳过检查
        静态配置在启动时已导入到 dynamic_skip_domains 表
        """
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc.lower()
            if not domain:
                return False

            # 统一动态跳过检查（Phase 2 统一方案）
            from app.config import get_settings
            if get_settings().dynamic_skip_enabled:
                from app.services.processor.domain_skip import domain_skip_service
                # 使用同步的缓存检查，避免在同步上下文中使用异步调用
                if domain_skip_service._skipped_domains_cache is not None:
                    return domain in domain_skip_service._skipped_domains_cache

            return False
        except Exception:
            # URL 解析失败时不跳过，让后续逻辑正常处理
            return False

    def __init__(self):
        # 常用RSS源配置
        self.known_sources = {
            "openai": {
                "name": "OpenAI Blog",
                "url": "https://openai.com/blog/rss.xml",
                "category": "ai",
            },
            "techcrunch": {
                "name": "TechCrunch",
                "url": "https://techcrunch.com/feed/",
                "category": "tech",
            },
            "36kr": {
                "name": "36Kr",
                "url": "https://36kr.com/feed/",
                "category": "tech",
            },
            "theverge": {
                "name": "The Verge",
                "url": "https://www.theverge.com/rss/index.xml",
                "category": "tech",
            },
            "wired": {
                "name": "Wired",
                "url": "https://www.wired.com/feed/rss",
                "category": "tech",
            },
        }
        
        # HTTP 客户端配置
        self.timeout = httpx.Timeout(30.0, connect=10.0)
    
    def _compute_url_hash(self, url: str) -> str:
        """
        计算URL哈希 (BLAKE2b-128)

        Args:
            url: 文章URL

        Returns:
            str: BLAKE2b-128哈希值 (16字符hex)
        """
        return hashlib.blake2b(url.encode(), digest_size=8).hexdigest()
    
    def _extract_domain(self, url: str) -> str:
        """
        提取URL的域名作为来源名
        
        Args:
            url: 文章URL
        
        Returns:
            str: 域名
        """
        parsed = urlparse(url)
        return parsed.netloc or "unknown"
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """
        解析RSS日期字符串
        
        RSS通常使用多种日期格式，此处尝试常见格式
        
        Args:
            date_str: 日期字符串
        
        Returns:
            datetime or None: 解析后的日期
        """
        if not date_str:
            return None
        
        cleaned = date_str.replace(" +0000", " GMT").replace(" +0000", "")
        # 常见日期格式
        date_formats = [
            "%Y-%m-%d %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S %z",    # RFC 822
            "%a, %d %b %Y %H:%M:%S GMT",  # RFC 822 (GMT)
            "%Y-%m-%dT%H:%M:%S%z",         # ISO 8601
            "%Y-%m-%dT%H:%M:%SZ",          # ISO 8601 (UTC)
            "%Y-%m-%d %H:%M:%S",           # 简单格式
            "%Y-%m-%d",                    # 仅日期
        ]

        dt = None
        for fmt in date_formats:
            try:
                # 尝试移除时区信息简化处理
                dt = datetime.strptime(cleaned, fmt)
                # return datetime.strptime(cleaned, fmt)
            except (ValueError, TypeError):
                continue
        
        # 如果都失败，记录警告
        if dt is None:
            logger.warning(f"无法解析日期: {date_str}")
            return None
        # 🔑 关键：如果是 naive，假设是 UTC 并添加时区信息
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        # 🔑 统一转换到 UTC，方便比较
        dt = dt.astimezone(timezone.utc)

        return dt
    
    async def fetch_feed(self, feed_url: str) -> Tuple[List[dict], bool, str]:
        """
        获取并解析 RSS 订阅源

        Args:
            feed_url: RSS 订阅源URL

        Returns:
            Tuple[List[dict], bool, str]:
                - 文章列表，每项包含:
                  - title: 标题
                  - url: 文章链接
                  - summary: 摘要
                  - content: 内容
                  - author: 作者
                  - published_at: 发布时间
                  - source_name: 来源名称
                  - url_hash: URL哈希
                - 是否成功
                - 错误信息（若失败）
        """
        logger.info(f"开始获取 RSS 源: {feed_url}")

        try:
            # 使用 feedparser 解析 (同步操作，但在async中使用)
            # feedparser 内部会处理HTTP请求
            feed = feedparser.parse(feed_url)

            # 检查解析错误（bozo = broken）
            if feed.bozo and feed.bozo_exception:
                error_msg = str(feed.bozo_exception)
                logger.warning(f"RSS 解析异常: {error_msg}")
                return [], False, error_msg

            # 获取源信息
            feed_title = feed.feed.get("title", "")

            results = []
            for entry in feed.entries:
                # 提取文章信息
                article = await self._parse_entry(
                    entry=entry,
                    feed_title=feed_title,
                    feed_url=feed_url
                )
                if article:
                    results.append(article)

            logger.info(
                f"RSS 源 {feed_title} 解析完成，获取 {len(results)} 篇文章"
            )
            return results, True, ""

        except Exception as e:
            error_msg = str(e)
            logger.error(f"获取 RSS 源失败: {feed_url}, 错误: {error_msg}")
            return [], False, error_msg

    async def fetch_feed_incremental(
        self,
        feed_url: str,
        last_modified: Optional[str] = None,
        etag: Optional[str] = None,
    ) -> Tuple[List[dict], bool, str, Optional[str], Optional[str]]:
        """
        获取并解析 RSS 订阅源（增量检测版本）

        使用 HTTP 条件请求（If-Modified-Since / If-None-Match）减少无效请求

        Args:
            feed_url: RSS 订阅源URL
            last_modified: 上次请求的 Last-Modified 头（可选）
            etag: 上次请求的 ETag 头（可选）

        Returns:
            Tuple[List[dict], bool, str, Optional[str], Optional[str]]:
                - 文章列表
                - 是否成功
                - 错误信息（若失败）
                - 新的 Last-Modified 头（若有）
                - 新的 ETag 头（若有）

        注意:
            - 返回 (articles, True, "", None, None) 表示无更新（304）
            - 返回 (articles, False, error_msg, None, None) 表示请求失败
        """
        logger.info(f"开始增量获取 RSS 源: {feed_url}")

        try:
            # 使用 httpx 发送带条件请求的 HTTP 请求
            headers = {}
            if last_modified:
                headers["If-Modified-Since"] = last_modified
            if etag:
                headers["If-None-Match"] = etag

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(feed_url, headers=headers)

                # 304 Not Modified - 没有更新
                if response.status_code == 304:
                    logger.info(f"RSS 源无更新（304）: {feed_url}")
                    return [], True, "", last_modified, etag

                # 其他 HTTP 错误
                if response.status_code != 200:
                    error_msg = f"HTTP {response.status_code}"
                    logger.warning(f"RSS 源请求失败: {feed_url}, {error_msg}")
                    return [], False, error_msg, None, None

                # 提取响应头
                new_last_modified = response.headers.get("Last-Modified")
                new_etag = response.headers.get("ETag")

                # 解析 RSS 内容
                # feedparser 可以接受 bytes 或 str
                feed_content = response.content
                feed = feedparser.parse(feed_content)

                # 检查解析错误
                if feed.bozo and feed.bozo_exception:
                    error_msg = str(feed.bozo_exception)
                    logger.warning(f"RSS 解析异常: {error_msg}")
                    # 解析异常但仍有内容，继续处理
                    if not feed.entries:
                        return [], False, error_msg, new_last_modified, new_etag

                # 获取源信息
                feed_title = feed.feed.get("title", "")

                results = []
                for entry in feed.entries:
                    article = await self._parse_entry(
                        entry=entry,
                        feed_title=feed_title,
                        feed_url=feed_url
                    )
                    if article:
                        results.append(article)

                logger.info(
                    f"RSS 源 {feed_title} 增量解析完成，"
                    f"获取 {len(results)} 篇文章, "
                    f"Last-Modified={new_last_modified}, ETag={new_etag}"
                )

                return results, True, "", new_last_modified, new_etag

        except httpx.TimeoutException:
            error_msg = "请求超时"
            logger.error(f"获取 RSS 源超时: {feed_url}")
            return [], False, error_msg, None, None
        except httpx.RequestError as e:
            error_msg = f"请求错误: {str(e)}"
            logger.error(f"获取 RSS 源请求错误: {feed_url}, {error_msg}")
            return [], False, error_msg, None, None
        except Exception as e:
            error_msg = str(e)
            logger.error(f"获取 RSS 源失败: {feed_url}, 错误: {error_msg}")
            return [], False, error_msg, None, None
    
    # =========================================================================
    # Phase 1 优化: _is_pseudo_content 伪正文检测
    # =========================================================================

    @staticmethod
    def _is_pseudo_content(content: str) -> bool:
        """
        判断内容是否是伪正文（链接+元数据，无实质内容）

        识别规则：
        1. 内容为空
        2. HN 格式特征词（Article URL:、Comments URL:、Points:）
        3. 去除链接后剩余文字 < 50 字符
        4. 内容全部由 <a> 标签组成
        """
        if not content:
            return True

        # HN 格式特征
        hn_markers = ["Article URL:", "Comments URL:", "Points:", "by "]
        if any(marker in content for marker in hn_markers):
            return True

        # 去除 HTML 标签后检查
        soup = BeautifulSoup(content, "lxml")
        text = soup.get_text(separator=" ", strip=True)

        # 去除 URL 后检查剩余文字
        # Phase 4 N3 优化: 使用预编译的 regex 常量
        text_without_urls = _URL_PATTERN.sub("", text)
        text_without_urls = _WHITESPACE_PATTERN.sub(" ", text_without_urls).strip()

        if len(text_without_urls) < 50:
            return True

        # 检查是否全部是链接
        all_links = soup.find_all("a")
        if all_links:
            # 检查是否有非链接的实质文字
            has_text = False
            for elem in soup.descendants:
                if elem.string and elem.string.strip() and not elem.string.strip().startswith("http"):
                    has_text = True
                    break
            if not has_text:
                return True

        return False

    # =========================================================================
    # Phase 1 优化: _extract_content 内容提取
    # =========================================================================

    @staticmethod
    def _extract_content(entry: dict) -> str:
        """
        从 feedparser entry 提取 content 字段

        返回原始 content 值，不进行兜底填充
        """
        # 优先使用 content:encoded 或 Atom content
        if "content" in entry:
            content_data = entry["content"]
            if isinstance(content_data, list) and content_data:
                return content_data[0].get("value", "") if isinstance(content_data[0], dict) else getattr(content_data[0], "value", "")
            return str(content_data) if content_data else ""

        # Atom content_detail
        if "content_detail" in entry:
            content_detail = entry["content_detail"]
            if isinstance(content_detail, dict):
                return content_detail.get("value", "")
            return getattr(content_detail, "value", "")

        return ""

    # =========================================================================
    # Phase 3A 修正: _resolve_content 内容补全（采集阶段跳过 trafilatura）
    # =========================================================================

    async def _resolve_content(
        self,
        url: str,
        content: str,
        summary: str = ""
    ) -> str:
        """
        解析 content 完整性，判断是否需要后台补全

        Phase 3A 修正：采集阶段默认跳过 trafilatura
        仅做内容判断 + summary 兜底，网络补全完全交给后台任务

        判断逻辑：
        1. 内容完整 → 直接返回原 content
        2. 域名在跳过列表 → 直接返回原 content/summary
        3. 配置启用同步补全 → 同步调用 trafilatura（仅紧急情况）
        4. 不满足以上条件 → summary 兜底（后台异步补全）

        Args:
            url: 文章 URL
            content: 原始 content
            summary: RSS 摘要（用于兜底）

        Returns:
            str: 处理后的 content
        """
        # 快速检查：内容是否足够完整（复用 _parse_entry 的判断逻辑）
        if not self._is_pseudo_content(content) and content and len(content) >= 200:
            return content

        # 域名跳过检查（即使不补全也记录日志）
        if self._should_skip_enrichment(url):
            logger.info(f"域名在跳过列表中: {url}")
            # 有 summary 则兜底，否则返回原值
            return summary if not content else content

        # 采集阶段同步补全（仅当配置启用时）
        # Phase 3A 修正：默认关闭，避免多篇 8s 超时累积突破 30s 采集超时
        if self._is_immediate_enrichment_enabled():
            logger.info(f"采集阶段同步补全（紧急模式）: {url}")
            full = await self._try_trafilatura(url)
            if full:
                return full

        # 不补全或补全失败 → summary 兜底
        # Phase 3A 修正：采集阶段不调用 trafilatura，后台异步补全
        if summary:
            logger.info(f"使用 summary 兜底（后台将异步补全）: {url}")
            return summary

        return content

    @classmethod
    def _get_content_fetcher(cls):
        """类级延迟导入（单例模式），避免每次补全都重新导入"""
        if cls._content_fetcher_instance is None:
            from app.services.fetcher.content_fetcher import content_fetcher
            cls._content_fetcher_instance = content_fetcher
        return cls._content_fetcher_instance

    async def _try_trafilatura(self, url: str) -> Optional[str]:
        """
        尝试 Trafilatura 补全，失败返回 None

        Phase 1 PH1 优化：添加单篇独立超时控制
        避免单篇文章下载阻塞整体采集流程
        """
        try:
            content_fetcher = self._get_content_fetcher()
            return await asyncio.wait_for(
                content_fetcher.fetch_content(url),
                timeout=PER_ARTICLE_ENRICH_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.warning(
                f"单篇文章补全超时（{PER_ARTICLE_ENRICH_TIMEOUT}s），"
                f"可能是国内网络无法访问: {url}"
            )
            return None
        except Exception as e:
            logger.warning(f"Trafilatura 补全失败: {url}, 错误: {e}")
            return None

    # =========================================================================
    # Phase 1 核心: _parse_entry 重写
    # =========================================================================

    async def _parse_entry(
        self,
        entry: dict,
        feed_title: str,
        feed_url: str
    ) -> Optional[dict]:
        """解析单条 RSS 条目（优化版，内置补全）"""

        # 获取 URL
        url = entry.get("link", "")
        if not url:
            return None

        # 标题
        title = re.sub(r"\s+", " ", entry.get("title", "无标题")).strip()

        # content（不兜底）
        content = self._extract_content(entry)

        # summary 用于兜底
        summary = entry.get("description") or entry.get("summary") or ""
        summary = self._strip_html(summary)

        # Phase 3 PH3 优化：判断是否需要后台补全
        # 在调用 _resolve_content 之前标记，以便后台任务知道哪些文章需要补全
        needs_enrichment = self._is_pseudo_content(content) or \
                           not content or \
                           len(content) < 200

        # 内容补全（Phase 3A 修正：采集阶段跳过 trafilatura，summary 兜底）
        content = await self._resolve_content(url, content, summary)

        # Phase 3D 修正：补全成功后重新评估 needs_enrichment
        # 如果 _resolve_content 成功补全了内容（同步模式），则不需要后台补全
        # 如果返回了 summary（采集阶段不补全，后台异步补全），则需要后台补全
        if self._is_immediate_enrichment_enabled() and content and len(content) >= 200:
            # 同步模式补全成功，不再需要后台补全
            needs_enrichment = False
        elif not content:
            # 极端情况：_resolve_content 返回空（无 summary）
            if summary:
                logger.warning(f"内容补全失败，使用 summary 兜底: {url}")
                content = summary
                needs_enrichment = True  # 标记仍需后台补全
            else:
                logger.warning(f"内容补全失败且无 summary 兜底，文章将保存为空内容: {url}")

        # 作者
        author = entry.get("author") or ""
        if not author and entry.get("authors"):
            author = entry["authors"][0].get("name", "") if isinstance(entry["authors"], list) else ""

        # 日期
        published_at = self._parse_date(
            entry.get("published") or entry.get("updated")
        )

        return {
            "title": title,
            "url": url,
            "content": content,
            "summary": summary,                       # Phase 3 新增：保留原始 summary
            "needs_enrichment": needs_enrichment,     # Phase 3 新增：标记需要后台补全
            "author": author,
            "published_at": published_at or datetime.utcnow(),
            "source_name": feed_title or self._extract_domain(feed_url),
            "source": "rss",
            "url_hash": self._compute_url_hash(url),
        }

    # =========================================================================
    # 原有辅助方法
    # =========================================================================
    
    def _strip_html(self, html: str) -> str:
        """
        移除HTML标签
        
        简单实现，用于清理摘要
        
        Args:
            html: HTML字符串
        
        Returns:
            str: 纯文本
        """
        if not html:
            return ""
        
        # 使用BeautifulSoup清理
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text(separator=" ", strip=True)
        
        # 清理多余空白
        text = re.sub(r"\s+", " ", text).strip()
        
        return text
    
    async def fetch_multiple_feeds(
        self,
        feed_urls: List[str]
    ) -> Tuple[List[dict], List[Tuple[str, bool, str]]]:
        """
        获取多个RSS源 (并发限流)

        使用 Semaphore 限制并发数，避免过多连接导致限流

        Args:
            feed_urls: RSS源URL列表

        Returns:
            Tuple[List[dict], List[Tuple[str, bool, str]]]:
                - 合并后的文章列表
                - 每条源的解析结果: [(url, is_success, error_msg), ...]
        """
        from app.config import get_settings
        settings = get_settings()

        all_articles = []
        results = []

        semaphore = asyncio.Semaphore(settings.rss_concurrent_limit)

        async def fetch_with_limit(url: str) -> Tuple[str, List[dict], bool, str]:
            """带并发限制的采集"""
            async with semaphore:
                articles, is_success, error_msg = await self.fetch_feed(url)
                return url, articles, is_success, error_msg

        # 并发执行所有采集任务
        tasks = [fetch_with_limit(url) for url in feed_urls]
        task_results = await asyncio.gather(*tasks, return_exceptions=True)

        # 整理结果
        for result in task_results:
            if isinstance(result, Exception):
                # 异常处理 (理论上不应发生)
                results.append((str(result), False, str(result)))
            else:
                url, articles, is_success, error_msg = result
                all_articles.extend(articles)
                results.append((url, is_success, error_msg))

        # 按发布时间排序 (新的在前)
        all_articles.sort(
            key=lambda x: x.get("published_at", datetime.min),
            reverse=True
        )

        logger.info(f"多源采集完成，共 {len(all_articles)} 篇文章")
        return all_articles, results


# 创建全局采集器实例
rss_fetcher = RSSFetcher()
