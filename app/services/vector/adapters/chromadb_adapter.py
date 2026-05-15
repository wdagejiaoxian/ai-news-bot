# -*- coding: utf-8 -*-
"""
ChromaDB 向量数据库适配器

采用 ChromaDB PersistentClient，数据持久化到 storage/chromadb/。
支持异步操作，通过 asyncio.to_thread 将同步调用封装为异步。
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from .base import BaseVectorDBAdapter

logger = logging.getLogger(__name__)


class ChromaDBAdapter(BaseVectorDBAdapter):
    """
    ChromaDB 嵌入式模式适配器

    使用 PersistentClient 将数据持久化到本地文件系统。
    默认路径：storage/chromadb/
    """

    def __init__(self, persist_directory: str = "storage/chromadb"):
        self._persist_directory = persist_directory
        self._client: Optional[chromadb.PersistentClient] = None
        self._collections: dict[str, chromadb.Collection] = {}

    async def _ensure_client(self) -> chromadb.PersistentClient:
        """延迟初始化客户端，确保目录存在"""
        if self._client is None:
            os.makedirs(self._persist_directory, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=self._persist_directory,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            logger.debug("ChromaDB client initialized at %s", self._persist_directory)
        return self._client

    async def _get_collection(
        self, name: str, dimension: int | None = None
    ) -> chromadb.Collection | None:
        """获取集合。不存在且无 dimension 时返回 None 而非崩溃（幂等行为）"""
        if name not in self._collections:
            client = await self._ensure_client()
            try:
                self._collections[name] = client.get_collection(name)
                logger.debug("Retrieved existing collection: %s", name)
            except Exception:
                if dimension is None:
                    logger.warning(
                        "Collection '%s' does not exist and no dimension provided, returning None",
                        name,
                    )
                    return None
                self._collections[name] = client.create_collection(
                    name=name,
                    metadata={"hnsw:space": "cosine"},
                )
                logger.info("Created new collection: %s (dimension=%d)", name, dimension)
        return self._collections[name]

    async def create_collection(
        self, name: str, dimension: int, metadata: dict | None = None
    ) -> None:
        """创建向量集合（如果不存在则创建）"""
        try:
            client = await self._ensure_client()
            try:
                client.get_collection(name)
                logger.debug("Collection already exists: %s", name)
            except Exception:
                client.create_collection(
                    name=name,
                    metadata=metadata or {"hnsw:space": "cosine"},
                )
                logger.info("Created collection: %s", name)
        except Exception as e:
            logger.error("Failed to create collection '%s': %s", name, e)
            raise

    async def delete_collection(self, name: str) -> None:
        """删除向量集合"""
        try:
            client = await self._ensure_client()
            client.delete_collection(name)
            self._collections.pop(name, None)
            logger.info("Deleted collection: %s", name)
        except Exception:
            logger.warning("Collection '%s' not found or already deleted", name)
            self._collections.pop(name, None)

    async def add(
        self,
        collection: str,
        ids: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
        documents: list[str] | None = None,
    ) -> None:
        """批量添加向量"""
        if not ids:
            return
        coll = await self._get_collection(collection)
        if coll is None:
            logger.warning("Collection '%s' not available, skipping add", collection)
            return
        kwargs: dict = {
            "ids": ids,
            "embeddings": embeddings,
            "metadatas": metadatas,
        }
        if documents:
            kwargs["documents"] = documents
        try:
            await asyncio.to_thread(coll.add, **kwargs)
            logger.debug(
                "Added %d vectors to collection '%s'",
                len(ids),
                collection,
            )
        except Exception as e:
            logger.error(
                "Failed to add vectors to '%s': %s",
                collection,
                e,
            )
            raise

    async def query(
        self,
        collection: str,
        query_embedding: list[float],
        top_k: int = 10,
        filter_conditions: dict | None = None,
    ) -> list[dict]:
        """
        向量相似度检索

        ChromaDB cosine 距离 d → 相似度 score = 1 - d
        """
        coll = await self._get_collection(collection)
        if coll is None:
            logger.warning("Collection '%s' not available, returning empty results", collection)
            return []
        kwargs: dict = {
            "query_embeddings": [query_embedding],
            "n_results": top_k,
        }
        if filter_conditions:
            kwargs["where"] = filter_conditions
        try:
            result = await asyncio.to_thread(coll.query, **kwargs)
        except Exception as e:
            logger.error("Query failed on collection '%s': %s", collection, e)
            raise

        formatted: list[dict] = []
        if result.get("ids") and result["ids"][0]:
            for i in range(len(result["ids"][0])):
                entry: dict = {
                    "id": result["ids"][0][i],
                    "score": (
                        1.0 - result["distances"][0][i]
                        if result.get("distances")
                        else 0.0
                    ),
                    "metadata": (
                        result["metadatas"][0][i] if result.get("metadatas") else {}
                    ),
                }
                if result.get("documents") and result["documents"][0]:
                    entry["document"] = result["documents"][0][i]
                formatted.append(entry)

        logger.debug(
            "Query on '%s' returned %d results (top_k=%d)",
            collection,
            len(formatted),
            top_k,
        )
        return formatted

    async def get(self, collection: str, ids: list[str]) -> list[dict]:
        """按 ID 批量获取向量"""
        if not ids:
            return []
        coll = await self._get_collection(collection)
        if coll is None:
            logger.warning("Collection '%s' not available, returning empty results", collection)
            return []
        try:
            result = await asyncio.to_thread(
                coll.get,
                ids=ids,
                include=["embeddings", "metadatas", "documents"],
            )
        except Exception as e:
            logger.error("Failed to get vectors from '%s': %s", collection, e)
            raise

        formatted: list[dict] = []
        if result.get("ids"):
            for i in range(len(result["ids"])):
                formatted.append({
                    "id": result["ids"][i],
                    "metadata": result["metadatas"][i] if result.get("metadatas") else {},
                    "document": (
                        result["documents"][i]
                        if result.get("documents")
                        else None
                    ),
                    "embedding": (
                        result["embeddings"][i]
                        if result.get("embeddings") is not None
                        else None
                    ),
                })
        return formatted

    async def delete(self, collection: str, ids: list[str]) -> None:
        """按 ID 批量删除向量"""
        if not ids:
            return
        try:
            coll = await self._get_collection(collection)
            if coll is None:
                logger.warning("Collection '%s' not available, skipping delete", collection)
                return
            await asyncio.to_thread(coll.delete, ids=ids)
            logger.debug("Deleted %d vectors from '%s'", len(ids), collection)
        except Exception as e:
            logger.warning("Failed to delete vectors from '%s': %s", collection, e)

    async def count(self, collection: str) -> int:
        """获取集合中向量总数"""
        try:
            coll = await self._get_collection(collection)
            if coll is None:
                return 0
            return await asyncio.to_thread(coll.count)
        except Exception as e:
            logger.warning("Failed to count vectors in '%s': %s", collection, e)
            return 0

    async def health_check(self) -> bool:
        """健康检查：验证客户端可连接"""
        try:
            client = await self._ensure_client()
            await asyncio.to_thread(client.heartbeat)
            return True
        except Exception as e:
            logger.error("ChromaDB health check failed: %s", e)
            return False

    async def collection_exists(self, name: str) -> bool:
        """检查 collection 是否存在"""
        try:
            client = await self._ensure_client()
            client.get_collection(name)
            return True
        except Exception:
            return False
