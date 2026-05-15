# -*- coding: utf-8 -*-
"""
pytest 配置和 fixtures
"""
import asyncio
import os
import sys
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# 确保 app 模块在路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.models import Base, User, OperationLog


# 使用内存 SQLite 进行测试
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """创建事件循环 fixture"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """创建测试数据库引擎"""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
    )

    # 创建所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # 清理
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """创建测试数据库会话"""
    session_maker = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_maker() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def test_user(db_session: AsyncSession) -> User:
    """创建测试用户"""
    user = User(
        platform="web_panel",
        platform_id="test_user",
        name="test_user",
        is_web_panel_user=True,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def operation_logs(db_session: AsyncSession) -> list[OperationLog]:
    """创建多个测试日志"""
    logs = []
    for i in range(5):
        log = OperationLog(
            log_type="task_exec",
            log_level="INFO",
            task_name=f"fetch_ai_news",
            operator="scheduler",
            action="success" if i % 2 == 0 else "fail",
            detail=f'{{"duration_ms": {1000 + i}}}',
            ip_address="127.0.0.1",
        )
        db_session.add(log)
        logs.append(log)

    await db_session.commit()
    for log in logs:
        await db_session.refresh(log)
    return logs


@pytest.fixture
def mock_db_session(mocker):
    """Mock 数据库会话"""
    mock_session = mocker.AsyncMock()
    return mock_session
