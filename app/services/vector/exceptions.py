# -*- coding: utf-8 -*-
"""
向量服务自定义异常

定义向量数据库和 Embedding 服务相关的所有异常类型。
异常分层设计：VectorServiceError → EmbeddingError / VectorDBError

为什么分层：
- VectorServiceError：顶层基类，所有向量服务异常的公共父类
- EmbeddingError：Embedding 生成相关的异常（可细分为超时、全部不可用等）
- VectorDBError：向量数据库操作相关的异常
- DuplicateArticleDetected：业务异常，表示检测到语义重复文章
"""


class VectorServiceError(Exception):
    """向量服务基础异常"""
    pass


class EmbeddingError(VectorServiceError):
    """Embedding 生成失败"""
    pass


class AllEmbeddingModelsUnavailableError(EmbeddingError):
    """所有 Embedding 模型均不可用

    当注册表中所有模型连续失败次数达到阈值（≥5次），
    触发故障降级，模型从轮询列表移除。
    """

    def __init__(self, message: str = "所有 Embedding 模型均不可用"):
        self.message = message
        super().__init__(self.message)


class EmbeddingTimeoutError(EmbeddingError):
    """Embedding 请求超时

    单次 Embedding 请求超过 timeout 阈值（默认 60s）时触发。
    不立即标记模型为不可用，而是让 EmbeddingManager 重试，
    连续超时才会触发降级。
    """

    def __init__(self, model_name: str, timeout: float):
        self.model_name = model_name
        self.timeout = timeout
        super().__init__(f"Embedding 请求超时: model={model_name}, timeout={timeout}s")


class VectorDBError(VectorServiceError):
    """向量数据库操作失败"""
    pass


class VectorDBNotAvailableError(VectorDBError):
    """向量数据库不可用

    ChromaDB 连接失败、健康检查连续失败时触发。
    此时所有向量操作退化为降级策略：
    - 语义去重 → 跳过，允许入库
    - LLM 缓存 → 返回未命中，走正常 LLM 流程
    - 语义搜索 → 返回空列表
    """

    def __init__(self, message: str = "向量数据库不可用"):
        self.message = message
        super().__init__(self.message)


class DuplicateArticleDetected(VectorServiceError):
    """检测到语义重复文章

    在语义去重流程中，当 cosine 相似度 ≥ dedup_similarity_threshold（默认 0.88）时抛出。
    不阻断主流程，仅作为去重判断依据。

    Attributes:
        matched_article_id: 匹配到的已有文章 ID
        similarity: 实际相似度分数（0.0 ~ 1.0）
    """

    def __init__(
        self,
        matched_article_id: int | None = None,
        similarity: float = 0.0,
    ):
        self.matched_article_id = matched_article_id
        self.similarity = similarity
        super().__init__(
            f"语义重复: article_id={matched_article_id}, similarity={similarity:.3f}"
        )
