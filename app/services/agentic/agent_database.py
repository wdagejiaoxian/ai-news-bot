# -*- coding: utf-8 -*-
"""
Agent 数据库模块

借鉴 database.py 的设计模式，为 Agent 提供统一的 SQLite 连接管理
解决多 Agent 实例并发访问导致的 "database is locked" 问题
"""

import os
import sqlite3
import logging
from contextlib import contextmanager
from threading import Lock
from typing import Optional

logger = logging.getLogger(__name__)

# 默认数据库路径
DEFAULT_AGENT_DB_PATH = "storage/agent_memory.db"


class AgentDatabase:
    """
    Agent 数据库管理类

    借鉴 database.py 的设计，提供：
    - 单例模式的连接管理
    - SQLite 优化配置（WAL 模式、busy_timeout）
    - 连接生命周期管理
    - 线程安全的连接访问
    """

    _instance = None
    _lock = Lock()

    def __new__(cls, db_path: Optional[str] = None):
        """单例模式"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, db_path: Optional[str] = None):
        """初始化数据库管理器"""
        if self._initialized:
            return

        self._db_path = db_path or DEFAULT_AGENT_DB_PATH
        self._connection: Optional[sqlite3.Connection] = None
        self._conn_lock = Lock()
        self._initialized = True

        logger.info(f"AgentDatabase 初始化，数据库路径: {self._db_path}")

    def _ensure_directory(self):
        """确保数据库目录存在"""
        dir_path = os.path.dirname(os.path.abspath(self._db_path))
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)

    @property
    def connection(self) -> sqlite3.Connection:
        """获取数据库连接（延迟初始化）"""
        if self._connection is None:
            with self._conn_lock:
                if self._connection is None:
                    self._ensure_directory()

                    # 创建连接
                    self._connection = sqlite3.connect(
                        self._db_path,
                        check_same_thread=False,
                        timeout=30.0
                    )

                    # 配置 SQLite 优化参数
                    self._connection.execute("PRAGMA journal_mode=WAL")
                    self._connection.execute("PRAGMA busy_timeout=30000")
                    self._connection.execute("PRAGMA synchronous=NORMAL")
                    self._connection.execute("PRAGMA cache_size=-64000")  # 64MB 缓存
                    self._connection.execute("PRAGMA temp_store=MEMORY")  # 临时表存内存

                    logger.info(f"Agent SQLite 连接已创建，WAL 模式已启用: {self._db_path}")

        return self._connection

    @contextmanager
    def get_connection(self):
        """
        获取连接的上下文管理器

        用法:
            with agent_db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(...)
                conn.commit()
        """
        conn = self.connection
        try:
            yield conn
        except Exception as e:
            logger.error(f"数据库操作异常: {e}")
            raise

    def init_db(self):
        """初始化数据库（如果需要创建表）"""
        # Agent 数据库的表由 langgraph 自动创建
        # 这里只是确保连接可用
        _ = self.connection
        logger.info("Agent 数据库初始化完成")

    def close(self):
        """关闭数据库连接"""
        with self._conn_lock:
            if self._connection:
                try:
                    self._connection.close()
                    logger.info("Agent SQLite 连接已关闭")
                except Exception as e:
                    logger.error(f"关闭 Agent SQLite 连接失败: {e}")
                finally:
                    self._connection = None

    def __del__(self):
        """析构函数，确保连接被关闭"""
        self.close()


# 创建全局 Agent 数据库实例
agent_db = AgentDatabase()


def get_agent_connection() -> sqlite3.Connection:
    """获取 Agent 数据库连接的便捷函数"""
    return agent_db.connection


def init_agent_database():
    """初始化 Agent 数据库的便捷函数"""
    agent_db.init_db()


def close_agent_database():
    """关闭 Agent 数据库的便捷函数"""
    agent_db.close()