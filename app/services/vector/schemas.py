# -*- coding: utf-8 -*-
"""
向量服务 Pydantic 数据模型

用于：
- API 请求/响应序列化
- 跨模块数据传输
- 参数校验

与 SQLAlchemy 模型的区分：
- SQLAlchemy 模型：数据库持久化
- Pydantic 模型：内存中数据传输和校验
"""

from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, Field


class DedupResult(BaseModel):
    """
    语义去重结果

    由 VectorService.deduplicate() 返回
    """
    is_duplicate: bool = False
    matched_article_id: Optional[int] = None
    similarity_score: float = Field(default=0.0, ge=0.0, le=1.0, description="余弦相似度 0.0~1.0")


class CacheResult(BaseModel):
    """
    LLM 缓存查询结果

    由 VectorService.check_llm_cache() 返回
    """
    is_hit: bool = False
    cached_article_id: Optional[int] = None
    similarity_score: float = Field(default=0.0, ge=0.0, le=1.0)
    cached_data: Optional[dict] = Field(
        default=None,
        description="缓存数据，包含 summary/keywords/tags/score/score_reason 五个字段"
    )


class SearchFilters(BaseModel):
    """
    语义搜索过滤条件

    对应 ChromaDB 的 where 子句过滤条件
    """
    date_from: Optional[datetime] = Field(default=None, description="最早发布日期过滤")
    date_to: Optional[datetime] = Field(default=None, description="最晚发布日期过滤")
    score_min: Annotated[int | None, Field(ge=0, le=100)] = Field(default=None, description="最低评分过滤")
    score_max: Annotated[int | None, Field(ge=0, le=100)] = Field(default=None, description="最高评分过滤")
    tags: Optional[list[str]] = Field(default=None, description="标签列表过滤（任一匹配）")
    status: Optional[str] = Field(default="PROCESSED", description="文章状态过滤")
    source_type: Optional[str] = Field(default=None, description="来源类型过滤（如 rss/github）")


class SearchResult(BaseModel):
    """
    语义搜索结果

    返回给 API 调用方或 Agent 工具的结果
    """
    article_id: int
    title: str
    summary: Optional[str] = None
    similarity: float = Field(ge=0.0, le=1.0, description="向量相似度")
    score: Annotated[float | None, Field(ge=0, le=100)] = Field(default=None, description="文章评分 0-100")
    published_at: Optional[datetime] = None
    url: str
    source_name: Optional[str] = None


class RecommendResult(BaseModel):
    """
    相似文章推荐结果

    用于文章详情页「相关阅读」推荐
    """
    article_id: int
    title: str
    similarity: float = Field(ge=0.0, le=1.0, description="向量相似度")
    score: Annotated[float | None, Field(ge=0, le=100)] = Field(default=None)


class RAGContext(BaseModel):
    """
    Agent RAG 上下文片段

    用于注入 LLM 对话上下文，summary 字段已截断至约 200 tokens
    """
    article_id: int
    title: str
    summary: str = Field(max_length=500, description="摘要（已截断，约 200 tokens）")
    similarity: float = Field(ge=0.0, le=1.0)
    published_at: Optional[datetime] = None
    url: str


class ClusterResult(BaseModel):
    """
    聚类结果

    用于主题聚类和热点发现
    """
    cluster_id: int
    keywords: list[str] = Field(min_length=1, max_length=10, description="主题关键词（最多10个）")
    article_count: int = Field(ge=0, description="聚类内文章数量")
    avg_score: float = Field(ge=0.0, le=100.0, description="聚类内文章平均评分")
    hotness: float = Field(ge=0.0, description="热度值（由文章数×均分×时间衰减计算）")
    is_emerging: bool = Field(default=False, description="是否为新兴话题（本周有、上周无）")
    representative_ids: list[int] = Field(default_factory=list, description="代表性文章 ID 列表（最多5个）")


class VectorStats(BaseModel):
    """
    向量系统统计

    用于 Web 面板统计看板
    """
    total_vectors: int = 0
    articles_collection_count: int = 0
    github_collection_count: int = 0
    cache_hit_rate_24h: float = Field(
        default=0.0, ge=0.0, le=100.0,
        description="最近 24h 缓存命中率百分比"
    )
    dedup_block_rate_24h: float = Field(
        default=0.0, ge=0.0, le=100.0,
        description="最近 24h 去重拦截率百分比"
    )
    avg_embedding_latency_ms: float = Field(default=0.0, ge=0.0, description="平均 embedding 生成延迟（ms）")
    avg_search_latency_ms: float = Field(default=0.0, ge=0.0, description="平均向量检索延迟（ms）")
    vector_db_available: bool = False
    active_embedding_models: int = 0
