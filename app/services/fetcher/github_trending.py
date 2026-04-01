# -*- coding: utf-8 -*-
"""
GitHub Trending 数据采集模块

负责从 GitHub Trending 页面获取热门项目
支持按编程语言和时间范围筛选
"""

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class GitHubTrendingFetcher:
    """
    GitHub Trending 采集器
    
    功能:
    - 获取 GitHub 热门项目
    - 按编程语言筛选
    - 按时间范围筛选 (daily/weekly/monthly)
    
    使用 gtrending 库或直接请求 GitHub API
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.base_url = "https://api.github.com"
        
        # 请求头
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "AI-News-Bot/1.0",
        }
        
        # 如果有Token则添加认证
        if self.settings.github_token:
            self.headers["Authorization"] = f"token {self.settings.github_token}"
    
    def _compute_repo_hash(self, full_name: str, date: datetime) -> str:
        """
        计算项目唯一哈希
        
        用于去重，结合项目名和日期
        
        Args:
            full_name: 仓库全名 (如 "owner/repo")
            date: 采集日期
        
        Returns:
            str: SHA256哈希值
        """
        # 格式: "owner/repo-YYYY-MM-DD"
        content = f"{full_name}-{date.strftime('%Y-%m-%d')}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    async def fetch_trending(
        self,
        language: Optional[str] = None,
        time_range: str = "daily",
        limit: int = 50
    ) -> List[dict]:
        """
        获取 GitHub Trending 项目
        
        Args:
            language: 编程语言 (如 "Python", "JavaScript")
                     传 None 表示所有语言
            time_range: 时间范围 ("daily", "weekly", "monthly")
            limit: 返回数量限制
        
        Returns:
            List[dict]: 项目列表，每项包含:
                - full_name: 仓库全名
                - description: 描述
                - url: 项目URL
                - language: 主要语言
                - stars: 星标数
                - forks: Fork数
                - stars_today: 今日新增
        """
        # 尝试使用 gtrending 库
        try:
            return await self._fetch_with_gtrending(language, time_range, limit)
        except ImportError:
            logger.warning("gtrending 库未安装，使用 GitHub API 方式")
            return await self._fetch_with_api(language, time_range, limit)
        except Exception as e:
            logger.error(f"gtrending 采集失败: {e}，回退到 API 方式")
            return await self._fetch_with_api(language, time_range, limit)
    
    async def _fetch_with_gtrending(
        self,
        language: Optional[str],
        time_range: str,
        limit: int
    ) -> List[dict]:
        """
        使用 gtrending 库获取Trending
        
        Args:
            language: 编程语言
            time_range: 时间范围
            limit: 返回数量
        
        Returns:
            List[dict]: 项目列表
        """
        # 动态导入 (可选依赖)
        from gtrending import fetch_repos
        
        # gtrending 的 since 参数: "daily", "weekly", "monthly"
        repos_data = fetch_repos(
            language=language or "",
            since=time_range
        )
        
        results = []
        trending_date = datetime.now(timezone.utc)
        
        for i, repo in enumerate(repos_data):
            if i >= limit:
                break
            
            # 提取项目信息
            full_name = repo.get("fullname", "")
            if not full_name:
                full_name = f"{repo.get('repo', '')}"
            
            results.append({
                "full_name": full_name,
                "description": repo.get("description", ""),
                "url": repo.get("url", f"https://github.com/{full_name}"),
                "language": repo.get("language"),
                "stars": repo.get("stars", 0),
                "forks": repo.get("forks", 0),
                "stars_today": repo.get("stars_today", 0),
                "repo_hash": self._compute_repo_hash(full_name, trending_date),
                "trending_date": trending_date,
                "trending_range": time_range,
            })
        
        logger.info(
            f"使用 gtrending 采集到 {len(results)} 个 "
            f"{language or '全语言'} {time_range} Trending 项目"
        )
        return results
    
    async def _fetch_with_api(
        self,
        language: Optional[str],
        time_range: str,
        limit: int
    ) -> List[dict]:
        """
        使用 GitHub REST API 获取Trending
        
        通过搜索创建时间来近似Trending
        注意：这不是真正的Trending，但可以作为备选方案
        
        Args:
            language: 编程语言
            time_range: 时间范围
            limit: 返回数量
        
        Returns:
            List[dict]: 项目列表
        """
        # 计算时间范围
        date_range_map = {
            "daily": 1,    # 1天内
            "weekly": 7,   # 7天内
            "monthly": 30, # 30天内
        }
        days = date_range_map.get(time_range, 1)
        
        # 计算日期 (UTC)
        since_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        # 构建搜索查询
        # 按star排序，获取最近创建的项目
        query = f"created:>{since_date}"
        if language:
            query += f" language:{language}"
        
        # API 参数
        params = {
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": min(limit, 100),  # 最多100
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/search/repositories",
                headers=self.headers,
                params=params
            )
            
            # 检查响应状态
            response.raise_for_status()
            
            data = response.json()
            items = data.get("items", [])
        
        results = []
        trending_date = datetime.utcnow()
        
        for repo in items[:limit]:
            full_name = repo.get("full_name", "")
            
            results.append({
                "full_name": full_name,
                "description": repo.get("description", ""),
                "url": repo.get("html_url", ""),
                "language": repo.get("language"),
                "stars": repo.get("stargazers_count", 0),
                "forks": repo.get("forks_count", 0),
                "stars_today": 0,  # API无法直接获取今日新增
                "repo_hash": self._compute_repo_hash(full_name, trending_date),
                "trending_date": trending_date,
                "trending_range": time_range,
            })
        
        logger.info(
            f"使用 GitHub API 采集到 {len(results)} 个 "
            f"{language or '全语言'} {time_range} 项目"
        )
        return results
    
    async def fetch_multiple_languages(
        self,
        languages: List[str],
        time_range: str = "daily",
        limit_per_lang: int = 20
    ) -> List[dict]:
        """
        获取多个语言的Trending
        
        顺序请求每个语言，合并结果
        
        Args:
            languages: 语言列表
            time_range: 时间范围
            limit_per_lang: 每个语言的限制数量
        
        Returns:
            List[dict]: 合并后的项目列表
        """
        all_repos = []
        
        for lang in languages:
            try:
                repos = await self.fetch_trending(
                    language=lang,
                    time_range=time_range,
                    limit=limit_per_lang
                )
                all_repos.extend(repos)
            except Exception as e:
                logger.error(f"采集语言 {lang} 失败: {e}")
                continue
        
        # 按star数量排序
        all_repos.sort(key=lambda x: x["stars"], reverse=True)
        
        logger.info(
            f"多语言采集完成，共 {len(all_repos)} 个项目"
        )
        return all_repos


# 创建全局采集器实例
github_fetcher = GitHubTrendingFetcher()
