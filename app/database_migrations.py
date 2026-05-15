# -*- coding: utf-8 -*-
"""
数据库迁移脚本

用于在应用启动时自动检测并执行必要的数据库结构变更
"""

import logging
from sqlalchemy import text

logger = logging.getLogger(__name__)

# 迁移版本追踪
CURRENT_MIGRATION_VERSION = 1


async def get_table_columns(session, table_name: str) -> set:
    """
    获取指定表的所有列名

    Args:
        session: 数据库会话
        table_name: 表名

    Returns:
        set: 列名集合
    """
    try:
        result = await session.execute(text(f"PRAGMA table_info({table_name})"))
        columns = {row[1] for row in result.fetchall()}
        return columns
    except Exception as e:
        logger.error(f"获取表 {table_name} 列信息失败: {e}")
        return set()


async def column_exists(session, table_name: str, column_name: str) -> bool:
    """检查列是否存在"""
    columns = await get_table_columns(session, table_name)
    return column_name in columns


async def run_migrations(session):
    """
    执行所有待执行的数据库迁移

    Args:
        session: 数据库会话
    """
    logger.info("开始检查数据库迁移...")

    # ===== 迁移 001: articles 表添加 is_pushed_immediate 字段 =====
    if not await column_exists(session, "articles", "is_pushed_immediate"):
        try:
            await session.execute(text(
                "ALTER TABLE articles ADD COLUMN is_pushed_immediate BOOLEAN DEFAULT 0"
            ))
            logger.info("迁移 001: articles 表添加 is_pushed_immediate 字段成功")
        except Exception as e:
            logger.error(f"迁移 001 失败: {e}")
    else:
        logger.info("迁移 001: articles.is_pushed_immediate 字段已存在，跳过")

    # ===== 迁移 002: webhook_configs 表添加 is_pushed_immediate 字段 =====
    if not await column_exists(session, "webhook_configs", "is_pushed_immediate"):
        try:
            await session.execute(text(
                "ALTER TABLE webhook_configs ADD COLUMN is_pushed_immediate BOOLEAN DEFAULT 0"
            ))
            logger.info("迁移 002: webhook_configs 表添加 is_pushed_immediate 字段成功")
        except Exception as e:
            logger.error(f"迁移 002 失败: {e}")
    else:
        logger.info("迁移 002: webhook_configs.is_pushed_immediate 字段已存在，跳过")

    logger.info("数据库迁移检查完成")


def get_migration_version(session) -> int:
    """
    获取当前数据库迁移版本

    Args:
        session: 数据库会话

    Returns:
        int: 当前版本号，默认为 0
    """
    try:
        # 尝试获取迁移版本表
        result = session.execute(text(
            "SELECT version FROM migration_version WHERE id = 1"
        ))
        row = result.fetchone()
        if row:
            return row[0]
        return 0
    except Exception:
        return 0


def set_migration_version(session, version: int):
    """
    设置数据库迁移版本

    Args:
        session: 数据库会话
        version: 版本号
    """
    try:
        session.execute(text(
            "CREATE TABLE IF NOT EXISTS migration_version (id INTEGER PRIMARY KEY, version INTEGER)"
        ))
        session.execute(text(
            "INSERT OR REPLACE INTO migration_version (id, version) VALUES (1, :version)"
        ), {"version": version})
    except Exception as e:
        logger.error(f"设置迁移版本失败: {e}")