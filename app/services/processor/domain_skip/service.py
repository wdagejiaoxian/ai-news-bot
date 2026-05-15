"""
域名动态跳过服务

功能：
- 记录域名补全成功/失败
- 判断是否触发跳过
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from app.models import DynamicSkipDomain
from app.database import db
from app.config import get_settings

logger = logging.getLogger(__name__)


class DomainSkipService:
    """域名动态跳过服务"""

    def __init__(self):
        self.settings = get_settings()
        # 内存缓存：被跳过的域名集合（避免每次查询数据库）
        self._skipped_domains_cache: Optional[set] = None
        self._cache_updated_at: Optional[datetime] = None
        self._cache_ttl_seconds: int = 300  # 缓存5分钟

    async def record_success(self, domain: str) -> None:
        """记录补全成功，重置连续失败计数"""
        if not self.settings.dynamic_skip_enabled:
            return

        try:
            async with db.get_session() as session:
                # 查询或创建域名记录
                stmt = select(DynamicSkipDomain).where(
                    DynamicSkipDomain.domain == domain
                )
                result = await session.execute(stmt)
                domain_stat = result.scalar_one_or_none()

                if domain_stat is None:
                    # 首次成功，创建记录
                    domain_stat = DynamicSkipDomain(
                        domain=domain,
                        consecutive_failures=0,
                        total_success=1
                    )
                    session.add(domain_stat)
                else:
                    # 更新统计
                    domain_stat.consecutive_failures = 0  # 重置连续失败
                    domain_stat.total_success += 1

                await session.commit()

        except Exception as e:
            logger.warning(f"记录域名成功失败: {domain}, 错误: {e}")

    async def record_failure(self, domain: str, reason: str = "unknown") -> bool:
        """
        记录补全失败

        返回：是否应该跳过该域名
        """
        if not self.settings.dynamic_skip_enabled:
            return False

        try:
            async with db.get_session() as session:
                # 查询或创建域名记录
                stmt = select(DynamicSkipDomain).where(
                    DynamicSkipDomain.domain == domain
                )
                result = await session.execute(stmt)
                domain_stat = result.scalar_one_or_none()

                if domain_stat is None:
                    # 首次失败，创建记录
                    domain_stat = DynamicSkipDomain(
                        domain=domain,
                        consecutive_failures=1,
                        total_failures=1,
                        last_failure_at=datetime.now(timezone.utc)
                    )
                    session.add(domain_stat)
                else:
                    # 更新统计
                    domain_stat.consecutive_failures += 1
                    domain_stat.total_failures += 1
                    domain_stat.last_failure_at = datetime.now(timezone.utc)

                # 判断是否触发跳过
                should_skip = False
                threshold = self.settings.dynamic_skip_threshold

                if domain_stat.consecutive_failures >= threshold:
                    if not domain_stat.is_skip:
                        domain_stat.is_skip = True
                        domain_stat.skip_reason = f"连续失败{domain_stat.consecutive_failures}次"
                        domain_stat.skip_since = datetime.now(timezone.utc)
                        should_skip = True
                        self._invalidate_cache()
                        logger.warning(
                            f"域名 {domain} 因连续失败 {domain_stat.consecutive_failures} 次被动态跳过"
                        )

                await session.commit()
                return should_skip

        except Exception as e:
            logger.warning(f"记录域名失败失败: {domain}, 错误: {e}")
            return False

    async def is_domain_skipped(self, domain: str) -> bool:
        """检查域名是否被跳过（带缓存）"""
        if not self.settings.dynamic_skip_enabled:
            return False

        # 检查缓存
        if self._skipped_domains_cache is not None:
            if self._cache_updated_at is not None:
                cache_age = (datetime.now(timezone.utc) - self._cache_updated_at).total_seconds()
                if cache_age < self._cache_ttl_seconds:
                    return domain in self._skipped_domains_cache

        # 缓存失效，从数据库加载
        try:
            async with db.get_session() as session:
                stmt = select(DynamicSkipDomain.domain).where(
                    DynamicSkipDomain.is_skip == True
                )
                result = await session.execute(stmt)
                skipped_domains = {row[0] for row in result.all()}

                # 更新缓存
                self._skipped_domains_cache = skipped_domains
                self._cache_updated_at = datetime.now(timezone.utc)

                return domain in skipped_domains

        except Exception as e:
            logger.warning(f"检查域名跳过状态失败: {domain}, 错误: {e}")
            return False

    def _invalidate_cache(self) -> None:
        """使缓存失效"""
        self._skipped_domains_cache = None
        self._cache_updated_at = None

    async def _load_cache(self) -> None:
        """加载跳过域名缓存"""
        try:
            async with db.get_session() as session:
                stmt = select(DynamicSkipDomain.domain).where(
                    DynamicSkipDomain.is_skip == True
                )
                result = await session.execute(stmt)
                skipped_domains = {row[0] for row in result.all()}

                # 更新缓存
                self._skipped_domains_cache = skipped_domains
                self._cache_updated_at = datetime.now(timezone.utc)

        except Exception as e:
            logger.warning(f"加载域名缓存失败: {e}")

    async def has_records(self) -> bool:
        """
        检查 dynamic_skip_domains 表是否有数据

        用于判断是否需要从静态配置导入
        """
        try:
            async with db.get_session() as session:
                stmt = select(DynamicSkipDomain.id).limit(1)
                result = await session.execute(stmt)
                return result.scalar_one_or_none() is not None
        except Exception as e:
            logger.warning(f"检查域名记录失败: {e}")
            return False  # 表不存在或查询失败，返回 False 触发导入

    async def import_static_domain(self, domain: str) -> None:
        """
        导入单个静态域名到动态跳过表

        Args:
            domain: 域名（如 "medium.com"）
        """
        try:
            async with db.get_session() as session:
                # 检查是否已存在
                stmt = select(DynamicSkipDomain).where(
                    DynamicSkipDomain.domain == domain
                )
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing is None:
                    # 创建新记录，标记为跳过
                    domain_stat = DynamicSkipDomain(
                        domain=domain,
                        is_skip=True,
                        skip_reason="静态配置导入",
                        skip_since=datetime.now(timezone.utc)
                    )
                    session.add(domain_stat)
                    await session.commit()
                    logger.info(f"导入静态域名: {domain}")
                else:
                    logger.debug(f"域名已存在，跳过导入: {domain}")

        except Exception as e:
            logger.warning(f"导入静态域名失败: {domain}, 错误: {e}")

    async def initialize_from_config(self) -> None:
        """
        从静态配置增量导入域名到动态跳过表

        逻辑：
        1. 读取静态配置中的域名列表
        2. 查询表中已存在的域名
        3. 计算差集（新增域名）
        4. 批量插入新增域名
        5. 刷新缓存

        优化：
        - 增量更新：只导入新增域名，不删除已有域名
        - 批量插入：单次数据库连接，批量提交
        """
        if not self.settings.dynamic_skip_enabled:
            return

        try:
            # 从静态配置读取域名
            domains_str = self.settings.trafilatura_skip_domains
            if not domains_str:
                return

            config_domains = set(d.strip().lower() for d in domains_str.split("|") if d.strip())

            # 查询表中已存在的域名（单次查询）
            async with db.get_session() as session:
                stmt = select(DynamicSkipDomain.domain)
                result = await session.execute(stmt)
                existing_domains = {row[0] for row in result.all()}

            # 计算差集（新增域名）
            new_domains = config_domains - existing_domains

            if not new_domains:
                logger.info("静态配置无新增域名，跳过导入")
                return

            # 批量插入新增域名（单次连接）
            async with db.get_session() as session:
                for domain in new_domains:
                    domain_stat = DynamicSkipDomain(
                        domain=domain,
                        is_skip=True,
                        skip_reason="静态配置导入",
                        skip_since=datetime.now(timezone.utc)
                    )
                    session.add(domain_stat)
                await session.commit()

            # 刷新并加载缓存（确保启动后第一次检查能正确判断）
            await self._load_cache()

            logger.info(f"从静态配置导入 {len(new_domains)} 个新增域名")

        except Exception as e:
            logger.error(f"初始化域名跳过服务失败: {e}")
            # 不抛出异常，不阻塞启动
