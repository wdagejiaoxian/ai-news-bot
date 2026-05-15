# -*- coding: utf-8 -*-
"""
向量数据库配置服务（VectorConfigService）

统一管理 VectorDBConfig 的生命周期：
- 初始化默认配置（initialize_default）
- 添加配置（add_config）
- 激活配置（activate_config）
- 删除配置（delete_config）
- 同步 Embedding 模型可用性（sync_model_availability）
- 查询配置（get_all_configs / get_active_config）

Usage:
    from app.services.vector.config_service import config_service

    # 初始化默认配置（在应用启动时调用）
    await config_service.initialize_default()

    # 获取所有配置
    configs = await config_service.get_all_configs()

    # 添加新配置
    config = await config_service.add_config("chromadb", "storage/chromadb", 1024)

    # 激活配置
    config = await config_service.activate_config(config_id=1)

    # 删除配置
    result = await config_service.delete_config(config_id=2)
"""

import asyncio
import logging
from typing import Optional

from sqlalchemy import select, update, func, and_

from app.database import db
from app.models import VectorDBConfig as VectorDBConfigModel

logger = logging.getLogger(__name__)


class VectorConfigService:
    """
    向量数据库配置服务（单例）

    统一管理向量数据库配置的生命周期，确保：
    - 启动时总有一个可用的默认配置
    - 配置切换时同步 VectorDBManager 和 EmbeddingManager 状态
    - 配置删除时级联清理 ChromaDB collection
    """

    def __init__(self):
        self._initialized = False
        self._init_lock = asyncio.Lock()

    # ===== 公开方法 =====

    async def initialize_default(self) -> Optional[VectorDBConfigModel]:
        """
        初始化默认配置（幂等）

        逻辑：
        - count == 0 → 创建默认配置（dimension 来自 embedding 模型或 1024 兜底）
        - count > 0 且无激活配置 → 自动激活默认配置
        - count > 0 且有激活配置 → 仅同步 VectorDBManager 状态

        Returns:
            当前激活的配置（VectorDBConfig 模型实例）
        """
        async with self._init_lock:
            if self._initialized:
                return await self.get_active_config() or self._get_default_config()

            from app.services.vector.embedding_manager import embedding_manager
            from app.services.vector.vector_db_manager import vector_db_manager

            async with db.get_session() as session:
                # 查询配置数量
                count_result = await session.execute(
                    select(func.count(VectorDBConfigModel.id))
                )
                count = count_result.scalar() or 0

                if count == 0:
                    # 空表 → 创建默认配置
                    dim_source = "embedding_model"
                    if embedding_manager.is_available():
                        dim = embedding_manager.get_dimension()
                    else:
                        dim = 1024
                        dim_source = "fallback_1024"

                    new_config = VectorDBConfigModel(
                        db_type="chromadb",
                        connection_string="storage/chromadb",
                        dimension=dim,
                        is_active=True,
                        is_default=True,
                    )
                    session.add(new_config)
                    await session.flush()

                    # 同步 VectorDBManager 状态
                    await vector_db_manager.switch_config(dim, new_config.id)
                    logger.info(
                        "[VectorConfigService] 创建默认配置: id=%d, dimension=%d (来源: %s)",
                        new_config.id,
                        dim,
                        dim_source,
                    )
                    self._initialized = True
                    return new_config

                # 有配置但无激活 → 激活默认配置或 id 最小的配置
                active_result = await session.execute(
                    select(VectorDBConfigModel).where(VectorDBConfigModel.is_active == True)
                )
                active_config = active_result.scalar_one_or_none()

                if active_config is None:
                    # 查找默认配置
                    default_result = await session.execute(
                        select(VectorDBConfigModel).where(VectorDBConfigModel.is_default == True)
                    )
                    config_to_activate = default_result.scalar_one_or_none()

                    # 若无默认配置，激活 id 最小的
                    if config_to_activate is None:
                        min_id_result = await session.execute(
                            select(VectorDBConfigModel).order_by(VectorDBConfigModel.id.asc())
                        )
                        config_to_activate = min_id_result.scalar_one_or_none()

                    if config_to_activate:
                        config_to_activate.is_active = True
                        await session.flush()
                        logger.info(
                            "[VectorConfigService] 自动激活配置: id=%d, dimension=%d",
                            config_to_activate.id,
                            config_to_activate.dimension,
                        )

                        # 同步 VectorDBManager 状态
                        await vector_db_manager.switch_config(
                            config_to_activate.dimension,
                            config_to_activate.id,
                        )
                    else:
                        logger.warning("[VectorConfigService] 有配置数据但无法激活（数据异常）")
                        self._initialized = True
                        return None
                else:
                    # 有激活配置 → 仅同步 VectorDBManager 状态
                    await vector_db_manager.switch_config(
                        active_config.dimension,
                        active_config.id,
                    )
                    logger.debug(
                        "[VectorConfigService] 已激活配置同步: id=%d, dimension=%d",
                        active_config.id,
                        active_config.dimension,
                    )

                self._initialized = True
                return await self.get_active_config()

    async def add_config(
        self, db_type: str, connection_string: str, dimension: int
    ) -> VectorDBConfigModel:
        """
        添加新配置

        Args:
            db_type: 数据库类型（当前仅支持 chromadb）
            connection_string: 连接字符串
            dimension: 向量维度（必须 > 0）

        Returns:
            新创建的配置

        Raises:
            ValueError: 参数校验失败（dimension ≤ 0、不支持的 db_type、配置已存在）
        """
        # 参数校验
        if dimension <= 0:
            raise ValueError("维度必须大于 0")

        if db_type != "chromadb":
            raise ValueError("当前仅支持 chromadb")

        from app.services.vector.vector_db_manager import vector_db_manager

        async with db.get_session() as session:
            # 检查是否已存在相同配置（db_type + connection_string + dimension）
            existing = await session.execute(
                select(VectorDBConfigModel).where(
                    and_(
                        VectorDBConfigModel.db_type == db_type,
                        VectorDBConfigModel.connection_string == connection_string,
                        VectorDBConfigModel.dimension == dimension,
                    )
                )
            )
            if existing.scalar_one_or_none() is not None:
                raise ValueError("该配置已存在")

            # 插入新配置（非激活、非默认）
            new_config = VectorDBConfigModel(
                db_type=db_type,
                connection_string=connection_string,
                dimension=dimension,
                is_active=False,
                is_default=False,
            )
            session.add(new_config)
            await session.flush()

            # 根据新配置创建 ChromaDB collection
            try:
                await vector_db_manager.switch_config(dimension, new_config.id)
                logger.info(
                    "[VectorConfigService] 添加配置: id=%d, db_type=%s, dimension=%d",
                    new_config.id,
                    db_type,
                    dimension,
                )
            except Exception as e:
                logger.warning(
                    "[VectorConfigService] 添加配置成功但 collection 创建失败: %s",
                    e,
                )

            return new_config

    async def activate_config(self, config_id: int) -> VectorDBConfigModel:
        """
        激活指定配置

        Args:
            config_id: 配置 ID

        Returns:
            激活后的配置

        Raises:
            ValueError: 配置不存在
        """
        from app.services.vector.vector_db_manager import vector_db_manager

        async with db.get_session() as session:
            # 查询配置
            result = await session.execute(
                select(VectorDBConfigModel).where(VectorDBConfigModel.id == config_id)
            )
            config = result.scalar_one_or_none()

            if config is None:
                raise ValueError("配置不存在")

            # 事务内：先取消所有激活，再激活目标配置
            await session.execute(
                update(VectorDBConfigModel).where(
                    VectorDBConfigModel.is_active == True
                ).values(is_active=False)
            )
            config.is_active = True
            await session.flush()

            # 切换 VectorDBManager 配置
            await vector_db_manager.switch_config(config.dimension, config.id)

            # 同步 Embedding 模型可用性
            await self.sync_model_availability()

            logger.info(
                "[VectorConfigService] 激活配置: id=%d, dimension=%d",
                config.id,
                config.dimension,
            )
            return config

    async def delete_config(self, config_id: int) -> dict:
        """
        删除配置

        Args:
            config_id: 配置 ID

        Returns:
            {"deleted": True, "collections_removed": True/False}

        Raises:
            ValueError: 默认配置不支持删除 / 请先切换到其他配置
        """
        from app.services.vector.vector_db_manager import vector_db_manager

        async with db.get_session() as session:
            # 查询配置
            result = await session.execute(
                select(VectorDBConfigModel).where(VectorDBConfigModel.id == config_id)
            )
            config = result.scalar_one_or_none()

            if config is None:
                raise ValueError("配置不存在")

            # 检查 is_default
            if config.is_default:
                raise ValueError("默认配置不支持删除")

            # 检查 is_active
            if config.is_active:
                raise ValueError("请先切换到其他配置再删除")

            # 获取 collection 名称
            adapter = await vector_db_manager.get_adapter()
            articles_name = vector_db_manager.get_collection_name("articles")
            github_name = vector_db_manager.get_collection_name("github_repos")

            # 级联删除 ChromaDB collection（失败不阻塞 DB 删除）
            collections_removed = True
            try:
                await adapter.delete_collection(articles_name)
                await adapter.delete_collection(github_name)
                logger.info(
                    "[VectorConfigService] 删除 collection: %s, %s",
                    articles_name,
                    github_name,
                )
            except Exception as e:
                logger.warning(
                    "[VectorConfigService] 删除 collection 失败（DB 记录仍会删除）: %s",
                    e,
                )
                collections_removed = False

            # 删除 DB 记录
            await session.delete(config)
            logger.info("[VectorConfigService] 删除配置: id=%d", config_id)

            return {"deleted": True, "collections_removed": collections_removed}

    async def sync_model_availability(self) -> None:
        """
        根据激活配置的 dimension 同步 Embedding 模型可用性

        规则：
        - 维度匹配 → is_available=True
        - 维度不匹配 → is_available=False（INFO 日志）
        - 无激活配置 → 保持原状态
        """
        from app.services.vector.embedding_manager import embedding_manager

        active_config = await self.get_active_config()
        active_dim = active_config.dimension if active_config else None

        for m in embedding_manager._models_list:
            if active_dim is None:
                # 无激活配置，保持原状态
                continue
            elif m.dimension == active_dim:
                m.is_available = True
                logger.debug(
                    "Embedding 模型 %s/%s 可用（维度 %s 匹配）",
                    m.provider_name,
                    m.model_name,
                    active_dim,
                )
            else:
                m.is_available = False
                logger.info(
                    "Embedding 模型 %s/%s 不可用（维度 %d ≠ 当前配置 %d）",
                    m.provider_name,
                    m.model_name,
                    m.dimension,
                    active_dim,
                )

        # 可用性变更后重建轮询 cycle
        embedding_manager._rebuild_cycle()

    async def get_all_configs(self) -> list[dict]:
        """
        获取所有配置（含 collection 统计信息）

        Returns:
            配置列表，每项包含: id, db_type, connection_string, dimension,
            is_active, is_default, collection_names, articles_count, github_count, created_at
        """
        from app.services.vector.vector_db_manager import vector_db_manager

        async with db.get_session() as session:
            result = await session.execute(
                select(VectorDBConfigModel).order_by(VectorDBConfigModel.id.asc())
            )
            configs = result.scalars().all()

        adapter = None
        try:
            adapter = await vector_db_manager.get_adapter()
        except Exception:
            pass

        result_list = []
        for cfg in configs:
            # 动态获取 collection 名称（使用配置自己的 dimension）
            articles_name = f"chromadb_ai_news_bot_{cfg.dimension}_articles"
            github_name = f"chromadb_ai_news_bot_{cfg.dimension}_github_repos"

            articles_count = 0
            github_count = 0
            if adapter is not None:
                try:
                    # 使用配置的 dimension 临时创建 adapter（如果 adapter 尚未切换到该配置）
                    # 实际上 adapter 是共享的，所以这里直接用 adapter 查询
                    # 但需要注意 adapter 可能使用不同的 dimension
                    # 故直接用名称查询，collection 不存在返回 0
                    articles_count = await adapter.count(articles_name)
                    github_count = await adapter.count(github_name)
                except Exception:
                    pass

            result_list.append({
                "id": cfg.id,
                "db_type": cfg.db_type,
                "connection_string": cfg.connection_string,
                "dimension": cfg.dimension,
                "is_active": cfg.is_active,
                "is_default": cfg.is_default,
                "collection_names": {
                    "articles": articles_name,
                    "github_repos": github_name,
                },
                "articles_count": articles_count,
                "github_count": github_count,
                "created_at": cfg.created_at.isoformat() if cfg.created_at else None,
            })

        return result_list

    async def get_active_config(self) -> Optional[VectorDBConfigModel]:
        """获取当前激活的配置"""
        async with db.get_session() as session:
            result = await session.execute(
                select(VectorDBConfigModel).where(VectorDBConfigModel.is_active == True)
            )
            return result.scalar_one_or_none()

    def _get_default_config(self) -> Optional[VectorDBConfigModel]:
        """同步获取默认配置（需在 async context 外调用时用）"""
        return None


# 全局单例
config_service = VectorConfigService()