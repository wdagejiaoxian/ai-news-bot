# -*- coding: utf-8 -*-
"""
RSS 源自动发现模块

提供两种发现机制：
1. DirectRSSDetector - 直接检测网站是否提供 RSS
2. RSSHubDetector - 检测网站是否被 RSSHub 支持
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import urljoin, urlparse

import feedparser
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class DiscoveryResult:
    """发现结果"""
    direct_rss: List[str]  # 直接发现的 RSS URL
    rsshub_routes: List[str]  # RSSHub 发现的路由
    source_type: str  # 推荐的 source_type: "standard", "rsshub", 或 None
    message: str  # 提示信息
    rsshub_hint: Optional[str] = None  # RSSHub 数据库匹配提示（如 RSSHub 未运行时）


class DirectRSSDetector:
    """
    直接 RSS 检测器

    从网站页面中检测 RSS 链接
    """

    # 常见的 RSS/Atom URL 后缀
    COMMON_PATHS = [
        "/feed",
        "/rss",
        "/atom.xml",
        "/feed.xml",
        "/rss.xml",
        "/index.xml",
        "/blog/feed",
        "/posts/feed",
        "/articles/feed",
        "/news/feed",
        "/atom",
        "/feed/atom",
        "/rss2.xml",
    ]

    # 常见的 RSS MIME 类型
    RSS_MIME_TYPES = [
        "application/rss+xml",
        "application/atom+xml",
        "application/xml",
        "text/xml",
    ]

    def __init__(self, timeout: float = 5.0):
        self.timeout = httpx.Timeout(timeout, connect=3.0)

    async def detect(self, base_url: str) -> List[str]:
        """
        检测网站是否提供 RSS

        两阶段检测：
        1. 从 HTML <link> 标签提取 RSS URL
        2. 探测常见 RSS URL 模式

        Args:
            base_url: 网站首页 URL

        Returns:
            发现的 RSS URL 列表
        """
        results = []
        seen = set()

        # 阶段一：从 HTML 中提取 <link> 标签
        html_rss = await self._detect_from_html(base_url)
        for url in html_rss:
            if url not in seen:
                seen.add(url)
                results.append(url)

        # 阶段二：探测常见 URL 模式
        pattern_rss = await self._detect_from_patterns(base_url)
        for url in pattern_rss:
            if url not in seen:
                seen.add(url)
                results.append(url)

        logger.info(f"DirectRSSDetector: {base_url} 发现 {len(results)} 个 RSS URL")
        return results

    async def _detect_from_html(self, base_url: str) -> List[str]:
        """从 HTML 中提取 <link rel='alternate' type='application/rss+xml'> 标签"""
        results = []

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(base_url)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, 'lxml')
                link_tags = soup.find_all('link', rel='alternate')

                for tag in link_tags:
                    link_type = tag.get('type', '').lower()
                    href = tag.get('href', '')

                    # 检查是否是 RSS/Atom 类型
                    if any(mime in link_type for mime in self.RSS_MIME_TYPES):
                        if href:
                            # 处理相对路径
                            rss_url = urljoin(base_url, href)
                            results.append(rss_url)

        except Exception as e:
            logger.warning(f"HTML 解析失败: {base_url}, 错误: {e}")

        return results

    async def _detect_from_patterns(self, base_url: str) -> List[str]:
        """探测常见 RSS URL 模式"""
        # 构造候选 URL 列表
        parsed = urlparse(base_url)
        base = f"{parsed.scheme}://{parsed.netloc}"

        candidate_urls = []
        for path in self.COMMON_PATHS:
            candidate_urls.append(urljoin(base, path))

        # 并发探测
        valid_urls = await self._probe_urls(candidate_urls)

        return valid_urls

    async def _probe_urls(self, urls: List[str]) -> List[str]:
        """并发探测 URL 是否是有效 RSS"""
        results = []
        semaphore = asyncio.Semaphore(3)  # 限制并发数

        async def check_url(url: str) -> Optional[str]:
            async with semaphore:
                try:
                    async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                        response = await client.get(url)

                        # 只处理 200 响应
                        if response.status_code != 200:
                            return None

                        content_type = response.headers.get('content-type', '').lower()

                        # 检查 content-type 是否是 XML/RSS
                        if not any(mime in content_type for mime in ['xml', 'rss', 'atom']):
                            return None

                        # 验证是否是有效 RSS
                        if self._is_valid_rss(response.text):
                            return url

                except Exception:
                    pass

                return None

        # 并发执行
        tasks = [check_url(url) for url in urls]
        results = await asyncio.gather(*tasks)

        return [r for r in results if r is not None]

    def _is_valid_rss(self, content: str) -> bool:
        """验证内容是否是有效 RSS/Atom"""
        try:
            feed = feedparser.parse(content)

            # feedparser 的 bozo 字段表示是否有错误
            # 如果是有效的 feed，应该有 entries
            return len(feed.entries) > 0

        except Exception:
            return False


class RSSHubDetector:
    """
    RSSHub 路由检测器

    检测网站是否被 RSSHub 支持
    """

    # 域名关键词 -> 可能的 RSSHub 路由模板
    DOMAIN_ROUTE_MAP = {
        "twitter.com": "/twitter/user/{username}",
        "x.com": "/twitter/user/{username}",
        "youtube.com": "/youtube/channel/{channel_id}",
        "youtu.be": "/youtube/channel/{channel_id}",
        "instagram.com": "/instagram/user/{username}",
        "reddit.com": "/reddit/r/{subreddit}",
        "medium.com": "/medium/feed/@{username}",
        "bilibili.com": "/bilibili/user/{uid}",
        "zhihu.com": "/zhihu/hotlist",
        "weibo.com": "/weibo/user/{uid}",
        "github.com": "/github/trending",
        "dev.to": "/dev.to/{username}",
        "sspai.com": "/sspai/matrix",
        "36kr.com": "/36kr/newsflashes",
        "huxiu.com": "/huxiu/article",
        "juejin.cn": "/juejin/posts",
        "csdn.net": "/csdn/news",
        "infoq.cn": "/infoq/recommend",
        "producthunt.com": "/producthunt/today",
    }

    def __init__(self, rsshub_url: str = "http://localhost:1200", timeout: float = 5.0):
        self.rsshub_url = rsshub_url.rstrip("/")
        self.timeout = httpx.Timeout(timeout, connect=3.0)

    async def detect(self, url: str) -> tuple[List[str], Optional[str]]:
        """
        检测 URL 是否被 RSSHub 支持

        Args:
            url: 网站 URL 或域名

        Returns:
            (routes, rsshub_hint): 路由列表和 RSSHub 提示信息（如有）
        """
        # 提取域名
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        # 移除 www. 前缀
        if domain.startswith('www.'):
            domain = domain[4:]

        # Step 1: 查询数据库（domain 匹配）
        db_routes = await self._query_routes_by_domain(domain)

        # Step 2: 检查 RSSHub 状态
        from app.services.rsshub.manager import get_rsshub_manager

        if not get_rsshub_manager().is_running():
            # RSSHub 未运行
            if db_routes:
                return [], f"RSSHub 数据库中有 {len(db_routes)} 条匹配「{domain}」的路由，但 RSSHub 未运行。请先启动 RSSHub 服务。"
            return [], None

        # Step 3: RSSHub 运行中 → HTTP 验证数据库路由
        if db_routes:
            verified = await self._validate_routes(db_routes)
            if verified:
                logger.info(f"RSSHubDetector: {domain} 从数据库找到 {len(verified)} 条可用路由")
                return verified, None

        # Step 4: Fallback 到 DOMAIN_ROUTE_MAP
        fallback_routes = await self._detect_from_domain_map(domain)
        if fallback_routes:
            return fallback_routes, None

        return [], None

    async def _query_routes_by_domain(self, domain: str) -> List[str]:
        """
        从数据库查询匹配域名的路由

        Args:
            domain: 域名（如 twitter.com）

        Returns:
            匹配的路由 URL 列表（最多 20 条）
        """
        try:
            from app.database import db
            from app.models import RSSHubRoute
            from sqlalchemy import select

            async with db.get_session() as session:
                result = await session.execute(
                    select(RSSHubRoute.route_path)
                    .where(
                        RSSHubRoute.domain == domain,
                        RSSHubRoute.is_active == True,
                    )
                    .limit(20)
                )
                route_paths = [row[0] for row in result.all()]
                return [f"{self.rsshub_url}{rp}" for rp in route_paths]
        except Exception as e:
            logger.warning(f"数据库查询路由失败: {e}")
            return []

    async def _detect_from_domain_map(self, domain: str) -> List[str]:
        """
        从 DOMAIN_ROUTE_MAP 检测（fallback 兜底逻辑）

        Args:
            domain: 域名

        Returns:
            可用的路由 URL 列表
        """
        route_template = None
        for known_domain, template in self.DOMAIN_ROUTE_MAP.items():
            if known_domain in domain:
                route_template = template
                break

        if not route_template:
            logger.debug(f"RSSHubDetector: {domain} 未找到 DOMAIN_ROUTE_MAP 匹配")
            return []

        # 如果路由模板没有参数（如 /zhihu/hotlist），直接验证
        if '{' not in route_template:
            route_url = f"{self.rsshub_url}{route_template}"
            if await self._validate_route(route_url):
                logger.info(f"RSSHubDetector: {domain} 从 DOMAIN_ROUTE_MAP 找到: {route_template}")
                return [route_url]

        return []

    async def _validate_routes(self, route_urls: List[str]) -> List[str]:
        """
        批量验证路由，返回可用的路由 URL 列表

        Args:
            route_urls: 路由 URL 列表

        Returns:
            验证通过的路由 URL 列表（最多 5 条）
        """
        valid = []
        for url in route_urls:
            if await self._validate_route(url):
                valid.append(url)
                if len(valid) >= 5:
                    break
        return valid

    async def _validate_route(self, route_url: str) -> bool:
        """验证 RSSHub 路由是否可用"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(route_url)

                if response.status_code != 200:
                    return False

                # 检查是否是有效 RSS
                feed = feedparser.parse(response.text)
                return len(feed.entries) > 0

        except Exception as e:
            logger.warning(f"RSSHub 路由验证失败: {route_url}, {e}")
            return False


class RSSDiscoverer:
    """
    RSS 自动发现器

    组合 DirectRSSDetector 和 RSSHubDetector 的结果
    """

    def __init__(self, rsshub_url: str = "http://localhost:1200"):
        self.direct_detector = DirectRSSDetector()
        self.rsshub_detector = RSSHubDetector(rsshub_url)

    async def discover(self, url: str) -> DiscoveryResult:
        """
        自动发现 RSS 源

        两阶段发现：
        1. 直接检测网站 RSS
        2. 如果未发现，检测 RSSHub 支持

        Args:
            url: 网站 URL

        Returns:
            DiscoveryResult
        """
        logger.info(f"RSSDiscoverer: 开始发现 {url}")

        # 阶段一：直接检测
        direct_rss = await self.direct_detector.detect(url)

        if direct_rss:
            return DiscoveryResult(
                direct_rss=direct_rss,
                rsshub_routes=[],
                source_type="standard",
                message=f"发现 {len(direct_rss)} 个 RSS 源"
            )

        # 阶段二：检测 RSSHub
        rsshub_routes, rsshub_hint = await self.rsshub_detector.detect(url)

        if rsshub_routes:
            return DiscoveryResult(
                direct_rss=[],
                rsshub_routes=rsshub_routes,
                source_type="rsshub",
                message=f"发现 RSSHub 路由支持"
            )

        # 未发现（可能有 rsshub_hint）
        return DiscoveryResult(
            direct_rss=[],
            rsshub_routes=[],
            source_type=None,
            message=rsshub_hint or "未发现 RSS 源。请尝试手动输入 RSS URL 或使用 RSSHub",
            rsshub_hint=rsshub_hint,
        )


# 创建全局实例
rss_discoverer = RSSDiscoverer()
