# -*- coding: utf-8 -*-
"""
向量数据库管理器

适配器模式：封装底层向量数据库实现，向上层提供统一的接口。
支持多后端切换（ChromaDB / Milvus / Qdrant），健康检查自动降级。

降级策略（VectorDBNotAvailableError）：
- 语义去重 → 跳过，允许入库
- LLM 缓存 → 返回未命中，走正常 LLM 流程
- 语义搜索 → 返回空列表
"""

import asyncio
import logging
from typing import Optional

from app.database import db
from .adapters.base import BaseVectorDBAdapter
from .adapters.chromadb_adapter import ChromaDBAdapter
from .exceptions import VectorDBNotAvailableError

logger = logging.getLogger(__name__)

ADAPTER_MAP: dict[str, type[BaseVectorDBAdapter]] = {
    "chromadb": ChromaDBAdapter,
}


class VectorDBManager:
    """
    向量数据库管理器（单例）

    功能：
    - 适配器生命周期管理（初始化、切换、销毁）
    - 健康检查 + 自动降级（向量库不可用时优雅退化）
    - 定期巡检（每 30s 检查一次，恢复后自动重新启用）
    - 支持多维度 collection 操作（通过 switch_config 触发，collection 创建由 config_service 负责）
    """

    # 类属性（默认值）
    DEFAULT_DIMENSION = 1024
    DEFAULT_PREFIX = "ai_news_bot"
    DEFAULT_DB_TYPE = "chromadb"

    def __init__(self):
        self._adapter: Optional[BaseVectorDBAdapter] = None
        self._is_available = False
        self._initialized = False
        self._init_lock = asyncio.Lock()
        self._health_check_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        # Phase 2 新增：激活配置状态
        self._active_dimension: int | None = None
        self._active_config_id: int | None = None
        self._collection_cache: dict[str, str] = {}  # domain → full_collection_name
        logger.info("VectorDBManager 已创建")

    async def initialize(self) -> None:
        """
        初始化向量数据库连接（仅连接 + 健康检查，不查询配置、不创建 collection）

        幂等操作：重复调用无效果。
        配置查询和 collection 创建由 config_service.initialize_default() 负责。
        """
        if self._initialized:
            return

        async with self._init_lock:
            if self._initialized:
                return
            await self._connect()
            self._initialized = True
            self._start_health_check()

    async def _connect(self) -> None:
        """连接向量数据库（仅创建 adapter + 健康检查，不查询配置）"""
        try:
            self._adapter = ChromaDBAdapter(persist_directory="storage/chromadb")
            healthy = await self._adapter.health_check()
            self._is_available = healthy
            if healthy:
                logger.info("向量数据库连接成功")
            else:
                logger.warning("向量数据库不可用，进入降级模式")
                self._is_available = False
        except Exception as e:
            logger.warning("VectorDBManager 连接失败（进入降级模式）: %s", e)
            self._adapter = ChromaDBAdapter(persist_directory="storage/chromadb")
            self._is_available = False

    async def _ensure_collections(self) -> bool:
        """确保 articles 和 github_repos 两个 collection 存在"""
        if not self._adapter:
            return False
        try:
            for domain in ("articles", "github_repos"):
                name = self.get_collection_name(domain)
                await self._adapter.create_collection(
                    name=name,
                    dimension=self._active_dimension or self.DEFAULT_DIMENSION,
                    metadata={"hnsw:space": "cosine"},
                )
            return True
        except Exception as e:
            logger.warning("确保 collection 存在失败: %s", e)
            return False

    def get_collection_name(self, domain: str) -> str:
        """
        获取当前激活配置对应的完整 collection 名称

        命名格式: {db_type}_{prefix}_{dimension}_{domain}
        例: chromadb_ai_news_bot_1024_articles
        """
        if domain in self._collection_cache:
            return self._collection_cache[domain]

        dim = self._active_dimension or self.DEFAULT_DIMENSION
        name = f"{self.DEFAULT_DB_TYPE}_{self.DEFAULT_PREFIX}_{dim}_{domain}"
        self._collection_cache[domain] = name
        return name

    @property
    def active_dimension(self) -> int | None:
        """获取当前激活配置的向量维度"""
        return self._active_dimension

    def _clear_cache(self) -> None:
        """清除 collection 名称缓存（切换配置后调用）"""
        self._collection_cache.clear()

    async def switch_config(self, dimension: int, config_id: int) -> bool:
        """
        切换到新配置

        Args:
            dimension: 新的向量维度
            config_id: 配置 ID

        Returns:
            True = 切换成功，False = 切换失败
        """
        self._active_dimension = dimension
        self._active_config_id = config_id
        self._clear_cache()
        if await self._ensure_collections():
            logger.info("已切换到配置 id=%d, dimension=%d", config_id, dimension)
            return True
        logger.warning("切换到配置 id=%d 时 collection 创建失败", config_id)
        return False

    def _start_health_check(self) -> None:
        """启动定期健康检查协程"""

        async def _health_loop() -> None:
            while not self._shutdown_event.is_set():
                await asyncio.sleep(30)
                if self._shutdown_event.is_set():
                    break
                if self._adapter is None:
                    continue
                try:
                    healthy = await self._adapter.health_check()
                    if healthy and not self._is_available:
                        self._is_available = True
                        logger.info("向量数据库恢复可用")
                    elif not healthy and self._is_available:
                        self._is_available = False
                        logger.warning("向量数据库不可用，进入降级模式")
                    # Phase 2 新增：额外检查 collection 是否存在
                    if self._is_available and self._adapter:
                        try:
                            name = self.get_collection_name("articles")
                            exists = await self._adapter.collection_exists(name)
                            if not exists:
                                self._is_available = False
                                logger.warning(
                                    "Collection '%s' 不存在，向量功能降级",
                                    name,
                                )
                        except Exception:
                            pass
                except Exception:
                    if self._is_available:
                        self._is_available = False
                        logger.warning("向量数据库健康检查失败，进入降级模式")

        self._health_check_task = asyncio.create_task(_health_loop())
        logger.debug("向量数据库健康检查协程已启动")

    async def get_adapter(self) -> BaseVectorDBAdapter:
        """
        获取当前适配器

        Returns:
            BaseVectorDBAdapter 实例

        Raises:
            VectorDBNotAvailableError: 向量数据库不可用
        """
        if not self._is_available or self._adapter is None:
            raise VectorDBNotAvailableError("向量数据库不可用")
        return self._adapter

    def is_available(self) -> bool:
        """当前向量库是否可用"""
        return self._is_available

    async def shutdown(self) -> None:
        """关闭管理器，取消健康检查任务"""
        logger.info("VectorDBManager 关闭中...")
        self._shutdown_event.set()
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        self._initialized = False
        logger.info("VectorDBManager 已关闭")


vector_db_manager = VectorDBManager()