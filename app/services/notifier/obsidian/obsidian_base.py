# -*- coding: utf-8 -*-
"""
Obsidian 通知器公共基类和工具函数

提供：
- 文件哈希计算（去重）
- 文件路径生成
- 通用工具函数

供 obsidian_api.py（本地模式）和 obsidian_git.py（远程模式）使用
"""

import hashlib
import logging
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)


def compute_file_hash(content: str) -> str:
    """
    计算内容的 SHA-256 哈希值

    Args:
        content: 文件内容

    Returns:
        str: 内容的哈希值（64字符十六进制）
    """
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def generate_daily_filename() -> str:
    """
    生成日报文件名

    Returns:
        str: 文件名，格式为 YYYY-MM-DD.md
    """
    return f"{datetime.now().strftime('%Y-%m-%d')}.md"


def generate_weekly_filename(week_start: str, week_end: str) -> str:
    """
    生成周报文件名

    Args:
        week_start: 周开始日期
        week_end: 周结束日期

    Returns:
        str: 文件名，格式为 weekly-YYYY-MM-DD_to_YYYY-MM-DD.md
    """
    return f"weekly-{week_start}_to_{week_end}.md"


def generate_immediate_filename(title: Optional[str] = None) -> str:
    """
    生成即时推送文件名

    Args:
        title: 可选的文章标题，用于生成更有意义的文件名

    Returns:
        str: 文件名
    """
    if title:
        # 清理标题，保留前30个字符
        clean_title = ''.join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
        clean_title = clean_title[:30] or 'article'
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f"{timestamp}_{clean_title}.md"
    else:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f"immediate_{timestamp}.md"


def get_folder_for_push_type(
    push_type: str,
    daily_folder: str = "AI-News/Daily",
    weekly_folder: str = "AI-News/Weekly",
    immediate_folder: str = "AI-News/Immediate"
) -> str:
    """
    根据推送类型获取对应的文件夹路径

    Args:
        push_type: 推送类型 (daily/weekly/immediate)
        daily_folder: 日报文件夹
        weekly_folder: 周报文件夹
        immediate_folder: 即时推送文件夹

    Returns:
        str: 文件夹路径
    """
    folder_map = {
        "daily": daily_folder,
        "weekly": weekly_folder,
        "immediate": immediate_folder,
    }
    return folder_map.get(push_type, immediate_folder)


async def check_file_exists_in_vault(
    webhook_id: int,
    file_path: str,
    file_hash: str
) -> bool:
    """
    检查文件是否已存在于 Vault 中（用于去重）

    Args:
        webhook_id: Webhook ID
        file_path: 文件路径
        file_hash: 文件内容哈希

    Returns:
        bool: 文件是否存在
    """
    from sqlalchemy import select, and_
    from app.models import VaultFile

    try:
        from app.database import db

        async with db.get_session() as session:
            result = await session.execute(
                select(VaultFile).where(
                    and_(
                        VaultFile.webhook_id == webhook_id,
                        VaultFile.file_path == file_path,
                        VaultFile.file_hash == file_hash
                    )
                )
            )
            return result.scalar_one_or_none() is not None
    except Exception as e:
        logger.warning(f"检查文件存在失败: {e}")
        return False


async def record_vault_file(
    webhook_id: int,
    file_path: str,
    file_hash: str,
    push_type: str
) -> bool:
    """
    记录已推送的文件到 VaultFile 表

    Args:
        webhook_id: Webhook ID
        file_path: 文件路径
        file_hash: 文件内容哈希
        push_type: 推送类型

    Returns:
        bool: 是否记录成功
    """
    from sqlalchemy import insert
    from app.models import VaultFile

    try:
        from app.database import db

        async with db.get_session() as session:
            await session.execute(
                insert(VaultFile).values(
                    webhook_id=webhook_id,
                    file_path=file_path,
                    file_hash=file_hash,
                    push_type=push_type
                )
            )
            await session.commit()
            return True
    except Exception as e:
        logger.error(f"记录 Vault 文件失败: {e}")
        return False


def cleanup_old_vault_files(webhook_id: int, days: int = 30) -> int:
    """
    清理过期的 Vault 文件记录

    Args:
        webhook_id: Webhook ID
        days: 保留天数，默认30天

    Returns:
        int: 删除的记录数
    """
    from sqlalchemy import delete, and_
    from app.models import VaultFile
    from datetime import timedelta

    try:
        from app.database import db
        import asyncio

        cutoff_date = datetime.now() - timedelta(days=days)

        async def _cleanup():
            async with db.get_session() as session:
                await session.execute(
                    delete(VaultFile).where(
                        and_(
                            VaultFile.webhook_id == webhook_id,
                            VaultFile.created_at < cutoff_date
                        )
                    )
                )
                await session.commit()
                return True

        loop = asyncio.get_event_loop()
        return loop.run_until_complete(_cleanup())
    except Exception as e:
        logger.error(f"清理 Vault 文件失败: {e}")
        return 0
