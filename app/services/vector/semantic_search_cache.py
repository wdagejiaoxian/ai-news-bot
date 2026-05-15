# -*- coding: utf-8 -*-
"""
语义搜索缓存管理器

功能：
- LRU 缓存策略（超过上限时删除距离过期时间最短的缓存）
- TTL 自动过期
- 线程安全
- 可配置容量和 TTL

设计原则：
- 单例模式，全局共享缓存
- 线程安全，使用 threading.Lock
- LRU 策略：删除距离过期时间最短的缓存
- TTL 过期：每次访问检查，过期自动删除
"""

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Optional

from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """缓存条目"""
    value: Any
    expires_at: float
    created_at: float


class SemanticSearchCache:
    """
    语义搜索缓存管理器

    缓存语义搜索的完整结果，支持：
    - LRU 策略：超过容量时删除距离过期时间最短的缓存
    - TTL 过期：每次访问检查，过期自动删除
    - 线程安全：使用 threading.Lock

    单例模式，通过 semantic_search_cache 全局实例访问
    """

    _instance: Optional['SemanticSearchCache'] = None
    _lock = threading.Lock()

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        settings = get_settings()
        self._sessions: dict[str, CacheEntry] = {}
        self._max_sessions = settings.semantic_cache_max_sessions
        self._ttl = settings.semantic_cache_ttl_seconds
        self._data_lock = threading.Lock()
        self._initialized = True

        logger.info(
            "语义搜索缓存初始化: max_sessions=%d, ttl=%ds",
            self._max_sessions, self._ttl
        )

    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存

        Args:
            key: 缓存键

        Returns:
            缓存值，如果不存在或已过期返回 None
        """
        with self._data_lock:
            entry = self._sessions.get(key)
            if entry is None:
                return None

            # 检查 TTL
            if time.time() > entry.expires_at:
                del self._sessions[key]
                logger.debug("缓存过期: %s", key[:50])
                return None

            return entry.value

    def set(self, key: str, value: Any) -> None:
        """
        设置缓存

        Args:
            key: 缓存键
            value: 缓存值
        """
        with self._data_lock:
            # 如果已存在，先删除（更新时会删除旧键）
            if key in self._sessions:
                del self._sessions[key]

            # 如果超过上限，删除距离过期时间最短的
            if len(self._sessions) >= self._max_sessions:
                self._evict_nearest_expiration()

            # 添加新缓存
            self._sessions[key] = CacheEntry(
                value=value,
                expires_at=time.time() + self._ttl,
                created_at=time.time(),
            )

            logger.debug(
                "缓存写入: %s (当前 %d/%d)",
                key[:50], len(self._sessions), self._max_sessions
            )

    def _evict_nearest_expiration(self) -> None:
        """删除距离过期时间最短的缓存（LRU 策略）"""
        if not self._sessions:
            return

        # 找到最早过期的缓存
        nearest_key = min(
            self._sessions.keys(),
            key=lambda k: self._sessions[k].expires_at
        )
        del self._sessions[nearest_key]
        logger.info("LRU 清理缓存: %s", nearest_key[:50])

    def cleanup_expired(self) -> int:
        """
        清理过期缓存（定时任务调用）

        Returns:
            清理的缓存数量
        """
        with self._data_lock:
            now = time.time()
            expired_keys = [
                key for key, entry in self._sessions.items()
                if now > entry.expires_at
            ]

            for key in expired_keys:
                del self._sessions[key]

            if expired_keys:
                logger.info("清理过期缓存: %d 条", len(expired_keys))

            return len(expired_keys)

    def clear(self) -> None:
        """清除所有缓存"""
        with self._data_lock:
            count = len(self._sessions)
            self._sessions.clear()
            logger.info("清除所有缓存: %d 条", count)

    @property
    def size(self) -> int:
        """获取当前缓存数量"""
        return len(self._sessions)

    @property
    def max_size(self) -> int:
        """获取最大缓存数量"""
        return self._max_sessions

    @property
    def ttl(self) -> int:
        """获取 TTL 设置值（秒）"""
        return self._ttl


# 全局单例
semantic_search_cache = SemanticSearchCache()