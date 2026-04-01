# -*- coding: utf-8 -*-
"""
RSS 解析和数据采集模块

负责从 RSS 订阅源获取AI资讯
支持多种RSS格式和网站
"""

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import urlparse

import feedparser
import httpx
from bs4 import BeautifulSoup

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
    
    def __init__(self):
        # 常用RSS源配置
        self.known_sources = {
            "openai": {
                "name": "OpenAI Blog",
                "url": "https://openai.com/blog/rss.xml",
                "category": "ai",
            },
            "hackernews": {
                "name": "Hacker News",
                "url": "https://news.ycombinator.com/rss",
                "category": "tech",
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
        计算URL哈希
        
        用于去重和唯一标识
        
        Args:
            url: 文章URL
        
        Returns:
            str: SHA256哈希值 (前64字符)
        """
        return hashlib.sha256(url.encode()).hexdigest()[:64]
    
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
    
    async def fetch_feed(self, feed_url: str) -> List[dict]:
        """
        获取并解析 RSS 订阅源
        
        Args:
            feed_url: RSS 订阅源URL
        
        Returns:
            List[dict]: 文章列表，每项包含:
                - title: 标题
                - url: 文章链接
                - summary: 摘要
                - content: 内容
                - author: 作者
                - published_at: 发布时间
                - source_name: 来源名称
                - url_hash: URL哈希
        """
        logger.info(f"开始获取 RSS 源: {feed_url}")
        
        try:
            # 使用 feedparser 解析 (同步操作，但在async中使用)
            # feedparser 内部会处理HTTP请求
            feed = feedparser.parse(feed_url)

            # 检查解析错误
            if feed.bozo and feed.bozo_exception:
                logger.warning(
                    f"RSS 解析异常 (可能格式不标准): {feed.bozo_exception}"
                )
            
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
            return results
            
        except Exception as e:
            logger.error(f"获取 RSS 源失败: {feed_url}, 错误: {e}")
            return []
    
    async def _parse_entry(
        self, 
        entry: dict, 
        feed_title: str,
        feed_url: str
    ) -> Optional[dict]:
        """
        解析单条 RSS 条目
        处理各种RSS格式的差异
        
        Args:
            entry: RSS 条目
            feed_title: 订阅源标题
            feed_url: 订阅源URL
        
        Returns:
            dict or None: 解析后的文章
        """
        # 获取URL (优先使用 link)
        url = entry.get("link", "")
        if not url:
            return None
        
        # 计算哈希
        url_hash = self._compute_url_hash(url)
        
        # 获取标题
        title = entry.get("title", "无标题")
        if not title:
            title = "无标题"
        
        # 清理标题 (移除多余空白)
        title = re.sub(r"\s+", " ", title).strip()
        
        # 获取摘要/内容
        # RSS可能有多种字段，依次尝试
        summary = ""
        content = ""
        
        # 尝试 summary/detail/description
        if hasattr(entry, "summary"):
            summary = entry.summary or ""
        elif hasattr(entry, "description"):
            summary = entry.description or ""
        
        # 尝试 content (Atom 或 RSS 2.0 content:encoded)
        if hasattr(entry, "content"):
            # content 是列表，取第一个
            if isinstance(entry.content, list) and entry.content:
                content = entry.content[0].value or ""
            else:
                content = entry.content or ""
        elif hasattr(entry, "content_detail"):
            content = entry.content_detail.value if entry.content_detail else ""
        
        # 如果没有content，使用summary
        if not content:
            content = summary
        
        # 清理HTML标签
        summary = self._strip_html(summary)
        
        # 获取作者
        author = ""
        if hasattr(entry, "author"):
            author = entry.author or ""
        elif hasattr(entry, "authors") and entry.authors:
            author = entry.authors[0].get("name", "")
        
        # 解析发布时间
        published_at = None
        if hasattr(entry, "published"):
            published_at = self._parse_date(entry.published)
        elif hasattr(entry, "updated"):
            published_at = self._parse_date(entry.updated)
        
        # 获取来源名称
        source_name = feed_title or self._extract_domain(feed_url)
        
        return {
            "title": title,
            "url": url,
            "summary": summary[:200] if summary else "",  # 限制长度
            "content": content[:5000] if content else "",  # 限制长度
            "author": author,
            "published_at": published_at or datetime.utcnow(),
            "source_name": source_name,
            "source": "rss",
            "url_hash": url_hash,
        }
    
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
    ) -> List[dict]:
        """
        获取多个RSS源
        
        顺序请求所有源，合并结果
        
        Args:
            feed_urls: RSS源URL列表
        
        Returns:
            List[dict]: 合并后的文章列表
        """
        all_articles = []
        
        for url in feed_urls:
            try:
                articles = await self.fetch_feed(url)
                all_articles.extend(articles)
            except Exception as e:
                logger.error(f"获取 RSS 源失败: {url}, 错误: {e}")
                continue
        
        # 按发布时间排序 (新的在前)
        all_articles.sort(
            key=lambda x: x.get("published_at", datetime.min),
            reverse=True
        )
        
        logger.info(f"多源采集完成，共 {len(all_articles)} 篇文章")
        return all_articles
    
    async def fetch_hackernews_top(self, limit: int = 20) -> List[dict]:
        """
        获取 Hacker News Top 故事
        
        使用官方 Firebase API
        
        Args:
            limit: 返回数量
        
        Returns:
            List[dict]: 文章列表
        """
        try:
            # Hacker News Top Stories API
            async with httpx.AsyncClient(timeout=30.0) as client:
                # 获取 Top Stories IDs
                response = await client.get(
                    "https://hacker-news.firebaseio.com/v0/topstories.json"
                )
                response.raise_for_status()
                story_ids = response.json()[:limit]
                
                # 获取每个故事的详情
                articles = []
                for story_id in story_ids:
                    story_response = await client.get(
                        f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
                    )
                    story = story_response.json()
                    
                    if story and story.get("url"):
                        url_hash = self._compute_url_hash(story["url"])
                        
                        # 判断是否AI相关 (通过标题关键词)
                        title = story.get("title", "")
                        
                        # HN API 不提供发布时间，使用当前时间
                        published_at = datetime.fromtimestamp(
                            story.get("time", 0)
                        ) if story.get("time") else datetime.utcnow()
                        
                        articles.append({
                            "title": title,
                            "url": story.get("url", ""),
                            "summary": f"HN Score: {story.get('score', 0)}",
                            "content": "",
                            "author": story.get("by", ""),
                            "published_at": published_at,
                            "source_name": "Hacker News",
                            "source": "hackernews",
                            "url_hash": url_hash,
                        })
                
                logger.info(f"Hacker News Top 获取完成: {len(articles)} 篇")
                return articles
                
        except Exception as e:
            logger.error(f"获取 Hacker News 失败: {e}")
            return []


# 创建全局采集器实例
rss_fetcher = RSSFetcher()
