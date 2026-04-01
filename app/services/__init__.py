# -*- coding: utf-8 -*-
"""
数据采集服务模块
"""

from app.services.fetcher.github_trending import github_fetcher
from app.services.fetcher.rss_parser import rss_fetcher

__all__ = ["github_fetcher", "rss_fetcher"]
