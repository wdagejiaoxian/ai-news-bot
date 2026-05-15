# -*- coding: utf-8 -*-
"""
数据库模块
负责数据库连接、会话管理和初始化
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import logging
from typing import List

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models import Base

logger = logging.getLogger(__name__)


class Database:
    """
    数据库管理类
    
    负责：
    - 创建数据库引擎
    - 管理会话
    - 初始化数据库表
    """
    
    def __init__(self):
        self.settings = get_settings()
        self._engine = None
        self._session_maker = None
    
    @property
    def engine(self):
        """获取数据库引擎"""
        if self._engine is None:
            # 构建数据库URL
            db_url = self.settings.database_url

            # 确保存储目录存在
            if db_url.startswith("sqlite"):
                # 提取文件路径
                db_path = db_url.replace("sqlite+aiosqlite:///", "")
                if db_path:
                    dir_path = os.path.dirname(db_path)
                    if dir_path and not os.path.exists(dir_path):
                        os.makedirs(dir_path, exist_ok=True)

            # SQLite 特定配置
            connect_args = {}
            if "sqlite" in db_url:
                connect_args = {
                    "check_same_thread": False,
                    "timeout": 30,  # 等待锁的超时时间（秒）
                }

            # 创建异步引擎
            self._engine = create_async_engine(
                db_url,
                echo=self.settings.debug,
                connect_args=connect_args,
                pool_pre_ping=True,
            )

            # SQLite WAL 模式配置 - 大幅提升并发写入能力
            # 需要在连接后立即执行 pragma，这是 SQLite 多线程优化的关键
            if "sqlite" in db_url:
                from sqlalchemy import event

                @event.listens_for(self._engine.sync_engine, "connect")
                def set_sqlite_pragma(dbapi_connection, connection_record):
                    cursor = dbapi_connection.cursor()
                    cursor.execute("PRAGMA journal_mode=WAL")
                    cursor.execute("PRAGMA busy_timeout=30000")  # 30秒
                    cursor.execute("PRAGMA synchronous=NORMAL")
                    cursor.close()

        return self._engine
    
    @property
    def session_maker(self) -> async_sessionmaker[AsyncSession]:
        """获取会话工厂"""
        if self._session_maker is None:
            self._session_maker = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
        return self._session_maker
    
    async def init_db(self):
        """
        初始化数据库
        
        创建所有表结构
        """
        async with self.engine.begin() as conn:
            # 创建所有表 (如果不存在)
            await conn.run_sync(Base.metadata.create_all)
    
    async def drop_db(self):
        """
        删除所有数据库表
        
        警告：此操作会删除所有数据！
        """
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        获取数据库会话的上下文管理器
        
        用法:
            async with db.get_session() as session:
                result = await session.execute(...)
        
        Yields:
            AsyncSession: 数据库会话
        """
        async with self.session_maker() as session:
            try:
                yield session
                # 提交事务
                await session.commit()
            except Exception:
                # 回滚事务
                await session.rollback()
                raise
    
    async def get_raw_connection(self):
        """获取原始数据库连接 (用于某些特殊操作)"""
        return await self.engine.connect()
    
    async def close(self):
        """关闭数据库连接"""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_maker = None


# 创建全局数据库实例
db = Database()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI 依赖注入函数
    
    用法:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    
    Yields:
        AsyncSession: 数据库会话
    """
    async with db.get_session() as session:
        yield session


async def init_database():
    """
    初始化数据库表的便捷函数
    
    应该在应用启动时调用
    """
    await db.init_db()


async def close_database():
    """
    关闭数据库连接的便捷函数

    应该在应用关闭时调用
    """
    await db.close()


async def init_builtin_rss_sources() -> None:
    """
    初始化内置RSS源

    当 rss_sources 表为空时，将预设的降级源写入数据库。
    此函数在应用启动时调用，失败不应阻止应用启动。

    Returns:
        None

    Raises:
        Exception: 数据库操作异常（由调用方处理）
    """
    from app.config import get_settings
    from app.models import RSSSource
    from sqlalchemy import select, func

    settings = get_settings()
    builtin_sources_config = settings.get_builtin_rss_sources()

    if not builtin_sources_config:
        logger.info("未配置内置RSS源（BUILTIN_RSS_SOURCES），跳过初始化")
        return

    async with db.get_session() as session:
        try:
            # 检查表是否有数据
            result = await session.execute(select(func.count(RSSSource.id)))
            count = result.scalar() or 0

            if count > 0:
                logger.info(f"RSS源表已有 {count} 条记录，跳过内置源初始化")
                return

            # 插入内置源
            for source_config in builtin_sources_config:
                source = RSSSource(
                    name=source_config["name"],
                    url=source_config["url"],
                    category=source_config.get("category"),
                    source_type=source_config.get("source_type", "builtin"),
                    is_active=source_config.get("is_active", True),
                    fetch_interval=source_config.get("fetch_interval", 60),
                    created_at=func.now(),
                    updated_at=func.now(),
                )
                session.add(source)

            await session.commit()
            logger.info(f"已初始化 {len(builtin_sources_config)} 个内置RSS源")

        except Exception as e:
            logger.error(f"初始化内置RSS源失败: {e}")
            raise
