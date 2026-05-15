# -*- coding: utf-8 -*-
"""
Embedding 模型管理器

参考 llm_manager.py 设计模式：
- 单例模式，全局共享一个 EmbeddingManager 实例
- 从数据库加载已启用的 Embedding 模型配置
- 多模型注册 / 优先级排序 / 轮询调度
- 并发控制（每个模型独立信号量）
- 故障检测与自动降级（连续 5 次失败后标记为不可用）
- 批量 embedding 自动分片（不超过模型的 max_batch_size）

Usage:
    from app.services.vector import embedding_manager

    await embedding_manager.initialize()
    embeddings = await embedding_manager.embed(["hello", "world"])
"""

import asyncio
import logging
import time
from itertools import cycle
from typing import Optional

from app.config import get_settings
from app.database import db
from .embedding_providers import (
    BaseEmbeddingProvider,
    create_embedding_provider,
)
from .exceptions import (
    AllEmbeddingModelsUnavailableError,
    EmbeddingTimeoutError,
    EmbeddingError,
)

logger = logging.getLogger(__name__)


class EmbeddingModelConfig:
    """
    Embedding 模型运行时配置

    封装数据库中的 EmbeddingModel 记录，加载为运行时 Provider 实例。
    """

    def __init__(
        self,
        model_id: int,
        provider_name: str,
        model_name: str,
        api_key: str,
        api_base: str,
        dimension: int,
        max_concurrency: int = 3,
        max_batch_size: int = 20,
        priority: int = 10,
    ):
        self.model_id = model_id
        self.provider_name = provider_name
        self.model_name = model_name
        self.api_key = api_key
        self.api_base = api_base or ""
        self._dimension = dimension
        self._provider: Optional[BaseEmbeddingProvider] = None
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._max_batch_size = max_batch_size
        self.priority = priority
        self.consecutive_failures = 0
        self.is_available = True

    async def get_provider(self) -> BaseEmbeddingProvider:
        if self._provider is None:
            raise RuntimeError(f"Provider for model {self.model_name} not initialized")
        return self._provider

    async def init_provider(self) -> None:
        """初始化底层 Provider 实例"""
        self._provider = create_embedding_provider(
            provider=self.provider_name,
            model_name=self.model_name,
            api_key=self.api_key,
            api_base=self.api_base,
            dimension=self._dimension,
        )

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def max_batch_size(self) -> int:
        return self._max_batch_size

    def record_failure(self) -> None:
        """记录一次失败，连续失败达到 5 次则标记为不可用"""
        self.consecutive_failures += 1
        if self.consecutive_failures >= 5:
            self.is_available = False
            logger.warning(
                "Embedding 模型 %s/%s 连续失败 %d 次，已标记为不可用",
                self.provider_name,
                self.model_name,
                self.consecutive_failures,
            )

    def record_success(self) -> None:
        """记录一次成功，重置失败计数"""
        self.consecutive_failures = 0
        if not self.is_available:
            self.is_available = True
            logger.info(
                "Embedding 模型 %s/%s 恢复可用",
                self.provider_name,
                self.model_name,
            )


class EmbeddingManager:
    """
    Embedding 模型管理器（单例）

    功能：
    - 多模型注册 / 轮询调度（按 priority 排序）
    - 并发控制（每个模型独立信号量）
    - 故障检测与自动降级（连续 5 次失败后标记为不可用）
    - 批量 embedding 自动分片
    """

    def __init__(self):
        self._models: dict[int, EmbeddingModelConfig] = {}
        self._model_cycle: Optional[cycle] = None
        self._models_list: list[EmbeddingModelConfig] = []
        self._initialized = False
        self._init_lock = asyncio.Lock()
        logger.info("EmbeddingManager 已创建")

    async def initialize(self) -> None:
        """
        从数据库加载所有已启用的 Embedding 模型

        幂等操作：重复调用无效果。
        """
        if self._initialized:
            return

        async with self._init_lock:
            if self._initialized:
                return
            await self._load_models_from_db()
            self._initialized = True

    async def reload_model(self, model_id: int, action: str = "update") -> None:
        """
        细粒度同步：只更新单个模型，减少性能开销

        Args:
            model_id: 要同步的模型 ID
            action: "add" / "update" / "delete"
        """
        async with self._init_lock:
            if action == "delete":
                # 删除：直接从内存中移除
                self._models.pop(model_id, None)
                self._models_list = [m for m in self._models_list if m.model_id != model_id]
                logger.info("EmbeddingManager 已移除模型: id=%d", model_id)
                return

            # add / update: 从数据库重新加载该模型
            from app.models import EmbeddingModel
            from app.utils.crypto import decrypt_api_key
            from sqlalchemy import select

            try:
                async with db.get_session() as session:
                    result = await session.execute(
                        select(EmbeddingModel).where(EmbeddingModel.id == model_id)
                    )
                    db_model = result.scalar_one_or_none()

                if not db_model or not db_model.is_enabled:
                    # 模型被删除或已禁用：从内存中移除
                    self._models.pop(model_id, None)
                    self._models_list = [m for m in self._models_list if m.model_id != model_id]
                    logger.info("EmbeddingManager 已移除模型: id=%d (已禁用)", model_id)
                else:
                    try:
                        api_key = decrypt_api_key(db_model.api_key)
                    except Exception:
                        api_key = db_model.api_key
                        logger.debug("API Key 解密失败，使用密文: %s", db_model.model_name)

                    config = EmbeddingModelConfig(
                        model_id=db_model.id,
                        provider_name=db_model.provider,
                        model_name=db_model.model_name,
                        api_key=api_key,
                        api_base=db_model.api_base or "",
                        dimension=db_model.dimension,
                        max_concurrency=db_model.max_concurrency,
                        max_batch_size=db_model.max_batch_size,
                        priority=db_model.priority,
                    )
                    await config.init_provider()
                    self._models[db_model.id] = config

                    # 更新 _models_list（替换或添加）
                    self._models_list = [m for m in self._models_list if m.model_id != model_id]
                    self._models_list.append(config)

                    logger.info(
                        "EmbeddingManager 已同步模型: %s/%s (id=%d, action=%s)",
                        db_model.provider,
                        db_model.model_name,
                        db_model.id,
                        action,
                    )

                # 重新排序并更新 cycle
                self._models_list.sort(key=lambda m: m.priority, reverse=True)
                self._model_cycle = cycle(self._models_list) if self._models_list else None

            except Exception as e:
                logger.error("EmbeddingManager 同步模型失败: id=%d, error=%s", model_id, e)
                raise

    async def _load_models_from_db(self) -> None:
        """从数据库加载模型配置"""
        from app.models import EmbeddingModel
        from app.utils.crypto import decrypt_api_key
        from sqlalchemy import select

        try:
            async with db.get_session() as session:
                result = await session.execute(
                    select(EmbeddingModel).where(EmbeddingModel.is_enabled == True)
                )
                db_models = result.scalars().all()

            if not db_models:
                logger.warning("数据库中无已启用的 Embedding 模型，向量功能将不可用")
                return

            for db_model in db_models:
                try:
                    api_key = decrypt_api_key(db_model.api_key)
                except Exception:
                    api_key = db_model.api_key
                    logger.debug("API Key 解密失败，使用密文: %s", db_model.model_name)

                config = EmbeddingModelConfig(
                    model_id=db_model.id,
                    provider_name=db_model.provider,
                    model_name=db_model.model_name,
                    api_key=api_key,
                    api_base=db_model.api_base or "",
                    dimension=db_model.dimension,
                    max_concurrency=db_model.max_concurrency,
                    max_batch_size=db_model.max_batch_size,
                    priority=db_model.priority,
                )
                await config.init_provider()
                self._models[db_model.id] = config
                self._models_list.append(config)

            self._models_list.sort(key=lambda m: m.priority, reverse=True)

            logger.info(
                "EmbeddingManager 加载了 %d 个模型: %s",
                len(self._models_list),
                [m.model_name for m in self._models_list],
            )

            # Phase 4: 启动时根据激活配置过滤模型可用性
            # 注意：此逻辑覆盖了启动场景的维度过滤，运行时配置切换由
            # config_service.sync_model_availability() 处理（双向同步：匹配→恢复，不匹配→禁用）
            try:
                from app.services.vector.config_service import config_service

                active_config = await config_service.get_active_config()
                if active_config:
                    active_dim = active_config.dimension
                    for m in self._models_list:
                        if m.dimension != active_dim:
                            m.is_available = False
                            logger.info(
                                "Embedding 模型 %s/%s 启动时标记不可用（维度 %d ≠ 当前配置 %d）",
                                m.provider_name,
                                m.model_name,
                                m.dimension,
                                active_dim,
                            )
            except Exception as e:
                logger.warning("Embedding 模型维度过滤跳过: %s", e)

            # 维度过滤后重建 cycle（确保 cycle 反映最新可用性状态）
            self._rebuild_cycle()
        except Exception as e:
            logger.error("EmbeddingManager 从数据库加载模型失败: %s", e)
            raise

    def _rebuild_cycle(self) -> None:
        """重建轮询 cycle（在模型可用性变更后调用）"""
        self._model_cycle = cycle(self._models_list) if self._models_list else None

    def _get_next_available_model(self) -> EmbeddingModelConfig:
        """轮询获取下一个可用模型"""
        available = [m for m in self._models_list if m.is_available]
        if not available:
            raise AllEmbeddingModelsUnavailableError(
                "所有 Embedding 模型均不可用"
            )

        if self._model_cycle is None:
            self._model_cycle = cycle(self._models_list)

        # 尝试所有模型（包括不可用的），直到找到可用的
        for _ in range(len(self._models_list)):
            model = next(self._model_cycle)
            if model.is_available:
                return model

        raise AllEmbeddingModelsUnavailableError("所有 Embedding 模型均不可用")

    async def embed(
        self,
        texts: list[str],
        model_id: int | None = None,
    ) -> list[list[float]]:
        """
        生成 embedding（自动分片 + 轮询 + 并发控制）

        Args:
            texts: 文本列表
            model_id: 指定模型 ID，None 则按 priority 轮询可用模型

        Returns:
            embedding 向量列表（与 texts 一一对应）

        Raises:
            AllEmbeddingModelsUnavailableError: 无可用模型
            EmbeddingTimeoutError: embedding 超时
            EmbeddingError: 其他 embedding 错误
        """
        if not texts:
            return []

        if model_id is not None:
            model = self._models.get(model_id)
            if model is None or not model.is_available:
                raise AllEmbeddingModelsUnavailableError(
                    f"Model {model_id} not available"
                )
        else:
            model = self._get_next_available_model()

        start_time = time.time()
        settings = get_settings()
        try:
            async with model._semaphore:
                provider = await model.get_provider()
                result = await asyncio.wait_for(
                    provider.embed(texts),
                    timeout=settings.embedding_timeout,
                )
                model.record_success()
                elapsed_ms = (time.time() - start_time) * 1000
                logger.debug(
                    "Embedding 完成: %s/%s, %d texts, %.0fms",
                    model.provider_name,
                    model.model_name,
                    len(texts),
                    elapsed_ms,
                )
                return result
        except asyncio.TimeoutError:
            model.record_failure()
            raise EmbeddingTimeoutError(
                model_name=f"{model.provider_name}/{model.model_name}",
                timeout=settings.embedding_timeout,
            )
        except EmbeddingError:
            model.record_failure()
            raise
        except Exception as e:
            model.record_failure()
            raise EmbeddingError(
                f"Unexpected embedding error for {model.provider_name}/{model.model_name}: {e}"
            ) from e

    def is_available(self) -> bool:
        """是否有可用模型"""
        return any(m.is_available for m in self._models_list)

    def get_active_model_count(self) -> int:
        """获取可用模型数量"""
        return len([m for m in self._models_list if m.is_available])

    def get_dimension(self) -> int:
        """获取维度：优先使用激活配置，回退到第一个可用模型，最终兜底 1024"""
        try:
            from app.services.vector.vector_db_manager import vector_db_manager

            active = vector_db_manager.active_dimension
            if active:
                return active
        except Exception:
            pass

        for m in self._models_list:
            if m.is_available:
                return m.dimension
        return 1024


embedding_manager = EmbeddingManager()
