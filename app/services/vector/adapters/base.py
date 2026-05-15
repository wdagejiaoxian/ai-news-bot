# -*- coding: utf-8 -*-
"""
向量数据库适配器抽象基类

定义所有向量数据库后端必须实现的接口。
采用适配器模式，使向量数据库的切换（ChromaDB ↔ Milvus ↔ Qdrant）对上层透明。

接口设计原则：
- 所有方法均为 async（即使底层是同步库，也通过 asyncio.to_thread 包装）
- 返回格式统一（见 query 方法的返回格式约定）
- 健康检查独立，不依赖其他方法
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseVectorDBAdapter(ABC):
    """
    向量数据库适配器抽象接口

    所有向量数据库后端实现必须继承此类，并实现以下方法。
    """

    @abstractmethod
    async def create_collection(
        self,
        name: str,
        dimension: int,
        metadata: dict | None = None,
    ) -> None:
        """
        创建向量集合（如果不存在）

        Args:
            name: 集合名称
            dimension: 向量维度（创建时需指定，后续不可更改）
            metadata: 集合元数据（如 ChromaDB 的 {"hnsw:space": "cosine"}）
        """
        ...

    @abstractmethod
    async def delete_collection(self, name: str) -> None:
        """
        删除向量集合

        Args:
            name: 集合名称
        """
        ...

    @abstractmethod
    async def add(
        self,
        collection: str,
        ids: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
        documents: list[str] | None = None,
    ) -> None:
        """
        批量添加向量

        Args:
            collection: 集合名称
            ids: 向量 ID 列表（与 embeddings 一一对应）
            embeddings: 向量列表（二维列表，每项是一个向量）
            metadatas: 元数据列表（与 ids 一一对应）
            documents: 原始文档列表（可选，用于存储可展示的原文）
        """
        ...

    @abstractmethod
    async def query(
        self,
        collection: str,
        query_embedding: list[float],
        top_k: int = 10,
        filter_conditions: dict | None = None,
    ) -> list[dict]:
        """
        向量相似度检索

        返回格式统一为（屏蔽底层差异）：
        [
            {
                "id": str,           # 向量 ID
                "score": float,      # 余弦相似度（0.0 ~ 1.0，1.0 = 完全相同）
                "metadata": dict,    # 元数据
                "document": str | None,  # 原始文档（如果有）
            },
            ...
        ]

        注意：不同向量数据库的距离定义不同（余弦/欧氏/点积），
        ChromaDB 使用 cosine 距离，返回距离 d → score = 1 - d

        Args:
            collection: 集合名称
            query_embedding: 查询向量
            top_k: 返回最近邻数量
            filter_conditions: 过滤条件（格式同 ChromaDB where 子句）
        """
        ...

    @abstractmethod
    async def get(
        self,
        collection: str,
        ids: list[str],
    ) -> list[dict]:
        """
        按 ID 批量获取向量

        返回格式统一为：
        [
            {
                "id": str,
                "metadata": dict,
                "document": str | None,
                "embedding": list[float] | None,  # 如果支持获取原始向量
            },
            ...
        ]

        Args:
            collection: 集合名称
            ids: 向量 ID 列表
        """
        ...

    @abstractmethod
    async def delete(
        self,
        collection: str,
        ids: list[str],
    ) -> None:
        """
        按 ID 批量删除向量

        Args:
            collection: 集合名称
            ids: 向量 ID 列表
        """
        ...

    @abstractmethod
    async def count(self, collection: str) -> int:
        """
        获取集合中向量总数

        Args:
            collection: 集合名称

        Returns:
            向量总数（如果集合不存在则返回 0）
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """
        健康检查

        检查向量数据库是否可连接、是否可读写。
        不要在健康检查中执行破坏性操作。

        Returns:
            True = 健康，False = 不健康
        """
        ...

    @abstractmethod
    async def collection_exists(self, name: str) -> bool:
        """
        检查 collection 是否存在

        Args:
            name: collection 名称

        Returns:
            True = 存在，False = 不存在
        """
        ...
