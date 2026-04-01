# -*- coding: utf-8 -*-
"""
数据库模块
负责数据库连接、会话管理和初始化
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models import Base


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
            
            # 创建异步引擎
            self._engine = create_async_engine(
                db_url,
                echo=self.settings.debug,
                # SQLite特定配置
                connect_args={"check_same_thread": False} if "sqlite" in db_url else {},
                pool_pre_ping=True,
            )
        
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
