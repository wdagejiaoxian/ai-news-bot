# -*- coding: utf-8 -*-
"""
向量数据库适配器模块

提供统一的向量数据库接口，不同后端（ChromaDB/Milvus/Qdrant）通过适配器实现此接口。
"""

from .base import BaseVectorDBAdapter
from .chromadb_adapter import ChromaDBAdapter

__all__ = ["BaseVectorDBAdapter", "ChromaDBAdapter"]