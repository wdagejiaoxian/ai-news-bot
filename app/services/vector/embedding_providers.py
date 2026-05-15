# -*- coding: utf-8 -*-
"""
Embedding Provider 实现

支持多后端：Ollama（本地）、OpenAI 兼容 API（OpenAI/SiliconFlow/OpenRouter）。

设计原则：
- 每个 Provider 独立实现特定 API 协议
- 所有方法为 async，即使底层是同步库也通过 asyncio.to_thread 封装
- 向量维度由各 Provider 自己声明
- 批量 embedding 优先使用 API 的批量接口（单次 HTTP 请求）

为什么批量优先：
- Ollama /api/embed 支持 input: string[]
- OpenAI /embeddings 支持 input: string[]
- 减少 HTTP 开销，降低延迟
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional

import httpx

from app.config import get_settings
from .exceptions import EmbeddingError

logger = logging.getLogger(__name__)


class BaseEmbeddingProvider(ABC):
    """Embedding Provider 抽象基类"""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """向量维度（由子类声明）"""
        ...

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """
        批量生成 embedding

        Args:
            texts: 文本列表

        Returns:
            二维列表，每个内层列表是一个 embedding 向量

        Raises:
            EmbeddingError: 生成失败
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """
        健康检查

        Returns:
            True = 可用，False = 不可用
        """
        ...

    async def validate_with_embed(self, expected_dimension: int) -> tuple[bool, str, int]:
        """
        通过实际 embed 验证模型可用性和维度一致性

        Args:
            expected_dimension: 期望的向量维度

        Returns:
            (success, message, actual_dimension):
            - success=True 表示验证通过（即使维度不匹配，只要模型可用）
            - message 包含详情
            - actual_dimension 实际输出的维度
        """
        try:
            embeddings = await self.embed(["validation_text"])
            if not embeddings:
                return False, "返回空结果", 0

            actual_dimension = len(embeddings[0])

            if actual_dimension != expected_dimension:
                # 维度不匹配但模型可用，返回成功并携带实际维度
                return True, f"维度不匹配: 期望 {expected_dimension}, 实际 {actual_dimension}。将使用实际维度保存。", actual_dimension

            return True, "验证通过", actual_dimension
        except Exception as e:
            return False, str(e), 0


class OllamaEmbeddingProvider(BaseEmbeddingProvider):
    """
    Ollama 本地 Embedding Provider

    API: POST /api/embed
    Request Body: {"model": "nomic-embed-text", "input": "text"} 或 {"model": "...", "input": ["text1", "text2"]}
    Response Body: {"embeddings": [[0.1, 0.2, ...], ...]}
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model_name: str = "nomic-embed-text",
        dimension: int = 768,
    ):
        if base_url is None:
            base_url = get_settings().ollama_embedding_base_url
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        url = f"{self.base_url}/api/embed"
        settings = get_settings()
        try:
            async with httpx.AsyncClient(timeout=settings.embedding_timeout) as client:
                response = await client.post(
                    url,
                    json={"model": self.model_name, "input": texts},
                )
                response.raise_for_status()
                data = response.json()
                embeddings = data.get("embeddings")
                if not embeddings or len(embeddings) != len(texts):
                    raise EmbeddingError(
                        f"Ollama 返回 embedding 数量不匹配: expected {len(texts)}, "
                        f"got {len(embeddings) if embeddings else 0}"
                    )
                return embeddings
        except httpx.TimeoutException as e:
            raise EmbeddingError(f"Ollama embedding 超时: {e}") from e
        except httpx.HTTPStatusError as e:
            raise EmbeddingError(f"Ollama embedding HTTP 错误 {e.response.status_code}: {e}") from e
        except Exception as e:
            raise EmbeddingError(f"Ollama embedding 失败: {e}") from e

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception as e:
            logger.warning("Ollama health check failed: %s", e)
            return False


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    """
    OpenAI 兼容 Embedding Provider

    支持 OpenAI / SiliconFlow / OpenRouter 等兼容 OpenAI Embedding API 的后端。

    API: POST /v1/embeddings
    Request Body: {"model": "text-embedding-3-small", "input": "text"} 或 ["text1", "text2"]
    Response Body: {"data": [{"embedding": [0.1, 0.2, ...], ...}], ...}
    """

    def __init__(
        self,
        api_base: str,
        api_key: str,
        model_name: str = "text-embedding-3-small",
        dimension: int = 1536,
    ):
        # 移除末尾的 /v1 或 /v1/，避免重复拼接（embed() 会拼接 /v1/embeddings）
        api_base = api_base.rstrip("/")
        if api_base.endswith("/v1"):
            api_base = api_base[:-3]  # 移除末尾的 /v1
        elif api_base.endswith("/v1/"):
            api_base = api_base[:-4]  # 移除末尾的 /v1/

        self.api_base = api_base
        self.api_key = api_key
        self.model_name = model_name
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        url = f"{self.api_base}/v1/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    url,
                    json={"model": self.model_name, "input": texts},
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
                embeddings = [item["embedding"] for item in data.get("data", [])]
                if len(embeddings) != len(texts):
                    raise EmbeddingError(
                        f"OpenAI embedding 返回数量不匹配: expected {len(texts)}, got {len(embeddings)}"
                    )
                return embeddings
        except httpx.TimeoutException as e:
            raise EmbeddingError(f"OpenAI embedding 超时: {e}") from e
        except httpx.HTTPStatusError as e:
            raise EmbeddingError(f"OpenAI embedding HTTP 错误 {e.response.status_code}: {e}") from e
        except Exception as e:
            raise EmbeddingError(f"OpenAI embedding 失败: {e}") from e

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.api_base}/v1/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                return response.status_code == 200
        except Exception as e:
            logger.warning("OpenAI-compatible API health check failed: %s", e)
            return False


class SiliconFlowEmbeddingProvider(OpenAIEmbeddingProvider):
    """
    硅基流动 Embedding Provider

    兼容 OpenAI 接口格式，支持多种模型。
    维度: 由用户配置或默认 1024
    """

    def __init__(
        self,
        api_base: str = "https://api.siliconflow.cn/v1",
        api_key: str = "",
        model_name: str = "BAAI/bge-large-zh-v1.5",
        dimension: int = 1024,
    ):
        super().__init__(
            api_base=api_base,
            api_key=api_key,
            model_name=model_name,
            dimension=dimension,
        )


PROVIDER_MAP: dict[str, type[BaseEmbeddingProvider]] = {
    "ollama": OllamaEmbeddingProvider,
    "openai": OpenAIEmbeddingProvider,
    "siliconflow": SiliconFlowEmbeddingProvider,
    "openrouter": OpenAIEmbeddingProvider,
}


def create_embedding_provider(
    provider: str,
    model_name: str,
    api_key: str,
    api_base: str,
    dimension: int | None = None,
) -> BaseEmbeddingProvider:
    """
    Embedding Provider 工厂函数

    Args:
        provider: 提供商名称（ollama/openai/siliconflow/openrouter）
        model_name: 模型名称
        api_key: API 密钥
        api_base: API 地址
        dimension: 向量维度（可选，某些 Provider 自动推断）

    Returns:
        BaseEmbeddingProvider 实例

    Raises:
        ValueError: 不支持的 provider
    """
    provider_lower = provider.lower()
    if provider_lower not in PROVIDER_MAP:
        raise ValueError(
            f"Unknown embedding provider: {provider}。支持的: {list(PROVIDER_MAP.keys())}"
        )

    cls = PROVIDER_MAP[provider_lower]
    if provider_lower == "ollama":
        return OllamaEmbeddingProvider(
            base_url=api_base or get_settings().ollama_embedding_base_url,
            model_name=model_name,
            dimension=dimension or 768,
        )
    elif provider_lower == "siliconflow":
        return SiliconFlowEmbeddingProvider(
            api_base=api_base or "https://api.siliconflow.cn/v1",
            api_key=api_key,
            model_name=model_name,
            dimension=dimension or 1024,
        )
    else:
        return OpenAIEmbeddingProvider(
            api_base=api_base,
            api_key=api_key,
            model_name=model_name,
            dimension=dimension or 1536,
        )
