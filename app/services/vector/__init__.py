# -*- coding: utf-8 -*-
"""
向量服务模块

提供向量数据库和 Embedding 模型的基础设施：
- Embedding 模型管理（多模型注册、轮询调度、故障降级）
- 向量数据库管理（适配器模式，支持 ChromaDB/Milvus/Qdrant）
- 向量索引（文章向量异步写入向量库）
- 语义搜索服务（7 个业务场景的核心编排）

Phase 依赖链：
  Phase 0（环境）→ Phase 1（数据模型）→ Phase 2（向量DB）→ Phase 3（Embedding）
                  → Phase 4（管理+索引）→ Phase 5（核心服务）→ Phase 6-9

Usage:
    from app.services.vector import vector_service, embedding_manager, vector_db_manager, article_indexer

    await vector_db_manager.initialize()
    await embedding_manager.initialize()
    await article_indexer.start()

    result = await vector_service.deduplicate(title="...", content="...")
"""

from .embedding_manager import EmbeddingManager, embedding_manager
from .vector_db_manager import VectorDBManager, vector_db_manager
from .article_indexer import ArticleIndexer, article_indexer
from .vector_service import VectorService, vector_service
from .exceptions import (
    AllEmbeddingModelsUnavailableError,
    EmbeddingError,
    VectorDBError,
    VectorDBNotAvailableError,
    VectorServiceError,
)

__all__ = [
    "embedding_manager",
    "vector_db_manager",
    "article_indexer",
    "vector_service",
    "EmbeddingManager",
    "VectorDBManager",
    "ArticleIndexer",
    "VectorService",
    "VectorServiceError",
    "EmbeddingError",
    "AllEmbeddingModelsUnavailableError",
    "VectorDBError",
    "VectorDBNotAvailableError",
]