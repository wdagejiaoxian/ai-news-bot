# -*- coding: utf-8 -*-
"""
配置管理模块
负责加载和管理所有配置项，支持环境变量和 .env 文件
"""

from pathlib import Path
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    应用配置类

    使用 pydantic-settings 自动从环境变量加载配置
    支持 .env 文件配置
    """

    # =============================================================================
    # 第一部分：应用基础配置
    # =============================================================================
    # 应用的基本信息，影响 FastAPI 文档标题、版本显示等

    app_name: str = Field(default="AI News Bot", description="应用名称（显示在 Swagger UI 标题）")
    app_version: str = Field(default="1.0.0", description="应用版本号（显示在 Swagger UI）")
    debug: bool = Field(default=False, description="调试模式：开启时启用 Swagger UI 文档和详细日志")
    secret_key: str = Field(default="", description="JWT 密钥（必填，长度不低于 32 字符）")

    # ========== JWT Token 过期配置 ==========
    access_token_expire_minutes: int = Field(
        default=15,
        ge=1,
        description="Access Token 有效期（分钟）"
    )
    refresh_token_expire_days: int = Field(
        default=3,
        ge=1,
        description="Refresh Token 有效期（天）"
    )

    # =============================================================================
    # 第二部分：数据库与存储配置
    # =============================================================================
    # 数据库连接和文件存储路径

    database_url: str = Field(
        default="sqlite+aiosqlite:///storage/database.db",
        description="SQLite 数据库连接 URL"
    )
    report_storage_path: str = Field(
        default="storage/reports",
        description="生成的日报/周报文件存储目录路径"
    )

    # =============================================================================
    # 第三部分：LLM 配置
    # =============================================================================
    # LLM 相关配置：支持本地 Ollama 和数据库中配置的多 Provider
    # 注意：API Key 和并发配置已迁移至数据库管理，仅保留 Ollama 本地模型配置

    # --- 本地 Ollama 配置（用于摘要生成，可选）---
    ollama_base_url: Optional[str] = Field(
        default=None,
        description="Ollama 服务地址（如 http://localhost:11434），不配置则使用数据库中配置的 Provider"
    )
    ollama_model: str = Field(
        default="llama3",
        description="Ollama 本地模型名称"
    )

    # --- 以下为已弃用的 LLM API 配置（已迁移至数据库管理）---
    # openai_api_key / openai_api_base / openai_summary_model / openai_score_model
    # siliconflow_api_key / siliconflow_api_base / siliconflow_max_concurrent
    # openrouter_api_key / openrouter_api_base / openrouter_max_concurrent
    # modelscope_api_key / modelscope_api_base / modelscope_max_concurrent

    # =============================================================================
    # 第四部分：GitHub 配置
    # =============================================================================
    # GitHub Trending 采集相关配置

    github_token: Optional[str] = Field(
        default=None,
        description="GitHub API Token（可选，用于提高请求频率限制）"
    )
    default_github_languages: str = Field(
        default="Python|JavaScript|TypeScript|Go",
        description="默认监控的 GitHub 语言（用 | 分隔）"
    )

    # =============================================================================
    # 第五部分：企业微信配置（Agentic 对话功能）
    # =============================================================================
    # 企业微信自建应用配置，用于接收用户消息并回复（双向交互）
    # 配置路径：企业微信后台 -> 应用管理 -> 自建应用

    wecom_corp_id: str = Field(default="", description="企业 ID（CorpId）")
    wecom_agent_id: str = Field(default="", description="自建应用 AgentId")
    wecom_agent_secret: str = Field(default="", description="自建应用 Secret")
    wecom_token: str = Field(default="", description="企业微信回调 Token（用于接收消息时的签名校验）")
    wecom_aes_key: str = Field(default="", description="企业微信回调 EncodingAESKey（用于接收消息的加解密）")

    # =============================================================================
    # 第六部分：Web 面板配置
    # =============================================================================
    # 内置 Web 管理面板的访问凭证

    web_panel_username: str = Field(default="", description="Web 面板登录用户名")
    web_panel_password: str = Field(default="", description="Web 面板登录密码（必填）")

    # =============================================================================
    # 第七部分：CORS 跨域配置
    # =============================================================================
    # 允许的跨域请求来源，用于前端访问后端 API

    cors_allowed_origins: str = Field(
        default="http://localhost:3000,http://localhost:8080",
        description="允许的 CORS 来源（多个用逗号分隔），生产环境应配置实际域名"
    )
    cors_allow_credentials: bool = Field(
        default=True,
        description="是否允许跨域请求携带凭证（cookies）"
    )

    # =============================================================================
    # 第八部分：定时任务调度配置
    # =============================================================================
    # 控制各类定时任务的执行时间，使用 cron 表达式或 interval 间隔

    # --- 采集任务 ---
    fetch_ai_news_interval: int = Field(
        default=30,
        description="AI 资讯 RSS 采集间隔（分钟）"
    )
    process_pending_interval: int = Field(
        default=20,
        description="待处理内容处理间隔（分钟）"
    )
    fetch_github_hour: int = Field(default=22, description="每日 GitHub Trending 采集小时（0-23）")
    fetch_weekly_github_hour: int = Field(default=7, description="每周 GitHub Trending 采集小时（0-23）")

    # --- 推送任务 ---
    daily_report_hour: int = Field(default=23, description="日报推送小时（0-23）")
    daily_report_minute: int = Field(default=40, description="日报推送分钟（0-59）")
    weekly_report_hour: int = Field(default=8, description="周报推送小时（0-23）")
    weekly_report_day: int = Field(default=0, description="周报推送日期（0=周一，6=周日）")

    # --- 清理任务 ---
    cleanup_hour: int = Field(default=3, description="低分文章清理任务执行小时（0-23）")
    cleanup_expired_data_hour: int = Field(default=4, description="过期数据清理任务执行小时（0-23）")
    cleanup_days_threshold_min: int = Field(
        default=7,
        description="低分文章清理阈值（天数）：超过此天数且评分比推送阈值低 20 分的文章会被清理"
    )
    cleanup_days_threshold_max: int = Field(
        default=30,
        description="过期文章清理阈值（天数）：超过此天数且评分比推送阈值低 10 分的文章会被清理"
    )

    # --- 日志保留配置 ---
    push_log_retention_days: int = Field(
        default=90,
        ge=1,
        le=365,
        description="推送日志保留天数，超期自动清理"
    )
    task_history_retention_days: int = Field(
        default=90,
        ge=1,
        le=365,
        description="任务执行历史保留天数，超期自动清理"
    )
    operation_log_retention_days: int = Field(
        default=90,
        ge=1,
        le=365,
        description="操作日志保留天数，超期自动清理"
    )

    # --- 向量任务 ---
    cluster_cron_hour: int = Field(default=3, description="每日主题聚类任务执行小时（0-23）")
    reindex_cron_hour: int = Field(default=4, description="每日向量对账任务执行小时（0-23）")

    # --- 定时任务公共配置 ---
    default_cron_minute: int = Field(default=0, description="所有定时任务默认分钟数（0-59）")

    # =============================================================================
    # 第九部分：推送与评分配置
    # =============================================================================
    # 内容推送阈值和评分相关配置

    push_score_threshold: int = Field(
        default=85,
        description="内容价值保留基线：低分文章清理任务以此值为基准计算删除阈值，高于此值的文章不会被清理"
    )

    # =============================================================================
    # 第十部分：RSS 源配置
    # =============================================================================
    # RSS 订阅源配置，包括内置降级源和并发采集控制

    builtin_rss_sources: str = Field(
        default="",
        description="内置 RSS 源配置（用 | 分隔），格式: name,url,category,source_type,is_active,fetch_interval"
    )
    rss_concurrent_limit: int = Field(
        default=5,
        description="RSS 源并发采集数（同时采集的 RSS 源数量）"
    )
    rss_error_threshold: int = Field(
        default=5,
        description="RSS 源连续错误次数阈值，达到后自动禁用该源"
    )
    rss_fetch_timeout: float = Field(
        default=30.0,
        description="单个 RSS 源采集超时时间（秒）"
    )

    # =============================================================================
    # 第十一部分：内容处理配置
    # =============================================================================
    # 文章内容处理、批次处理和保存优化配置

    process_batch_size: int = Field(
        default=5,
        description="内容处理每批处理文章数"
    )
    process_max_total: int = Field(
        default=45,
        description="内容处理每次任务最多处理文章总数"
    )
    process_batch_delay: float = Field(
        default=2.0,
        description="内容处理批次间延迟秒数（避免过快消耗资源）"
    )
    article_save_batch_size: int = Field(
        default=100,
        description="文章批量保存每批最大数量（超过此值将分批提交到数据库）"
    )

    # =============================================================================
    # 第十二部分：内容补全配置（Trafilatura 网页正文提取）
    # =============================================================================
    # 控制是否跳过某些域名，以及后台异步补全的行为

    trafilatura_skip_domains: str = Field(
        default="medium.com|news.ycombinator.com|bestblogs.dev|techcrunch.com|theverge.com",
        description="跳过 Trafilatura 补全的域名（用 | 分隔），这些域名在国内可能无法访问"
    )
    trafilatura_enable_immediate_enrichment: bool = Field(
        default=False,
        description="是否在 RSS 采集阶段同步补全文章内容（默认关闭，改为后台异步补全）"
    )
    enrich_concurrency: int = Field(
        default=3,
        description="后台内容补全最大并发数"
    )
    enrich_timeout: float = Field(
        default=15.0,
        description="单篇文章内容补全超时时间（秒）"
    )
    enrich_min_content_length: int = Field(
        default=100,
        description="内容补全结果最小字符数，低于此值视为补全失败"
    )

    # =============================================================================
    # 第十三部分：动态域名跳过配置（Domain Skip）
    # =============================================================================
    # 针对持续失败的 RSS 源域名，自动跳过避免重复尝试

    dynamic_skip_enabled: bool = Field(
        default=True,
        description="是否启用动态域名跳过（连续失败后自动跳过该域名）"
    )
    dynamic_skip_threshold: int = Field(
        default=5,
        description="连续失败次数阈值，达到后自动跳过该域名"
    )

    # =============================================================================
    # 第十四部分：RSSHub 配置
    # =============================================================================
    # RSSHub 服务集成配置，用于提供更丰富的 RSS 源聚合能力

    rsshub_enabled: bool = Field(
        default=True,
        description="是否启用 RSSHub 集成（关闭后 Web 面板不显示 RSSHub 相关功能）"
    )
    rsshub_url: str = Field(
        default="http://localhost:1200",
        description="RSSHub 服务地址"
    )
    rsshub_auto_start: bool = Field(
        default=True,
        description="是否在应用启动时自动启动 RSSHub（需要 Docker 环境）"
    )
    rsshub_health_check_interval: int = Field(
        default=30,
        ge=10,
        le=300,
        description="RSSHub 健康检查间隔（秒）"
    )
    rsshub_startup_timeout: int = Field(
        default=120,
        ge=30,
        le=600,
        description="RSSHub 启动等待超时时间（秒）"
    )
    rsshub_routes_file_path: str = Field(
        default="storage/rsshub_build/routes.json",
        description="RSSHub routes.json 文件在宿主机上的路径（Docker 卷挂载路径）"
    )
    rsshub_routes_static_path: str = Field(
        default="app/services/rsshub/routes_static.json",
        description="RSSHub 内置静态路由文件路径（用于离线降级）"
    )

    # =============================================================================
    # 第十五部分：语义搜索与向量配置
    # =============================================================================
    # 向量嵌入、语义搜索缓存和语义去重配置

    semantic_cache_max_sessions: int = Field(
        default=100,
        ge=10,
        le=1000,
        description="语义搜索缓存最大会话数（每个会合约 100KB）"
    )
    semantic_cache_ttl_seconds: int = Field(
        default=600,
        ge=60,
        le=3600,
        description="语义搜索缓存 TTL（秒），缓存超过此时间后失效"
    )
    semantic_search_max_results: int = Field(
        default=100,
        ge=20,
        le=200,
        description="语义搜索最大返回结果数（影响前端分页）"
    )
    embedding_max_text_length: int = Field(
        default=4000,
        description="Embedding 输入文本最大字符数，超过则降级为 title + summary 拼接"
    )

    # ========== Embedding 服务地址配置 ==========
    ollama_embedding_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama Embedding 服务地址，部署在不同机器时需修改"
    )

    dedup_similarity_threshold: float = Field(
        default=0.88,
        description="语义去重相似度阈值（0-1），向量相似度超过此值视为重复文章"
    )

    # ========== 语义缓存配置 ==========
    cache_similarity_threshold: float = Field(
        default=0.85,
        description="语义缓存命中相似度阈值（0-1），超过此值复用缓存的摘要/评分"
    )

    # ========== 超时配置 ==========
    embedding_timeout: float = Field(
        default=120.0,
        description="Embedding 生成超时时间（秒）"
    )
    llm_api_timeout: float = Field(
        default=30.0,
        description="LLM API 调用测试超时时间（秒）"
    )
    batch_llm_timeout: float = Field(
        default=120.0,
        description="批次 LLM 处理超时时间（秒），用于批量摘要/评分等耗时操作"
    )

    # ========== 重试配置 ==========
    llm_max_retries: int = Field(
        default=3,
        ge=0,
        description="LLM API 调用最大重试次数"
    )
    embedding_max_retries: int = Field(
        default=3,
        ge=0,
        description="Embedding 生成最大重试次数"
    )

    # ========== Webhook 超时配置 ==========
    webhook_api_timeout: float = Field(
        default=10.0,
        description="Webhook API 调用超时时间（秒），用于创建/测试/更新 Webhook 时的连接测试"
    )

    # ========== 企业微信超时配置 ==========
    wecom_webhook_timeout: float = Field(
        default=10.0,
        description="企业微信 Webhook 消息发送超时（秒）"
    )
    wecom_api_timeout: float = Field(
        default=30.0,
        description="企业微信 API 调用超时（秒），用于获取 token 和发送消息"
    )
    wecom_upload_timeout: float = Field(
        default=60.0,
        description="企业微信文件上传超时（秒）"
    )

    # ========== 企业微信 API 地址配置 ==========
    wecom_api_base_url: str = Field(
        default="https://qyapi.weixin.qq.com",
        description="企业微信 API 基础地址（需要代理时修改）"
    )

    # ========== 索引器配置 ==========
    indexer_concurrency: int = Field(
        default=3,
        ge=1,
        description="向量索引器并发处理数"
    )

    # ========== 命令配置 ==========
    command_default_limit: int = Field(
        default=10,
        ge=1,
        description="命令默认返回结果数（用于 /ai_news, /github, /search 等命令）"
    )
    command_preview_limit: int = Field(
        default=5,
        ge=1,
        description="命令预览结果数（用于 /today 等预览命令）"
    )

    # ========== 语义搜索配置 ==========
    semantic_search_top_k: int = Field(
        default=5,
        ge=1,
        description="语义搜索/去重返回的结果数量上限"
    )
    semantic_cache_top_k: int = Field(
        default=3,
        ge=1,
        description="语义缓存查找结果数量"
    )

    # ========== GitHub API 配置 ==========
    github_api_base_url: str = Field(
        default="https://api.github.com",
        description="GitHub API 基础地址"
    )

    # =============================================================================
    # 第十六部分：Pydantic 模型配置（必须放在最后）
    # =============================================================================

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,  # 环境变量不区分大小写
        extra="ignore"  # 忽略额外字段
    )

    # =============================================================================
    # 辅助方法
    # =============================================================================

    def get_github_languages(self) -> List[str]:
        """获取 GitHub 语言列表"""
        if not self.default_github_languages:
            return []
        return [s.strip() for s in self.default_github_languages.split("|") if s.strip()]

    def get_builtin_rss_sources(self) -> List[dict]:
        """
        获取内置 RSS 源配置列表

        Returns:
            List[dict]: 内置 RSS 源列表，每项包含 name, url, category, source_type, is_active, fetch_interval
        """
        if not self.builtin_rss_sources:
            return []
        sources = []
        for item in self.builtin_rss_sources.split("|"):
            item = item.strip()
            if not item:
                continue
            # 格式: name,url,category,source_type,is_active,fetch_interval
            parts = item.split(",")
            if len(parts) != 6:
                continue
            try:
                sources.append({
                    "name": parts[0].strip(),
                    "url": parts[1].strip(),
                    "category": parts[2].strip() or None,
                    "source_type": parts[3].strip(),
                    "is_active": parts[4].strip().lower() == "true",
                    "fetch_interval": int(parts[5].strip()) if parts[5].strip().isdigit() else 60
                })
            except (ValueError, IndexError):
                continue
        return sources


# 创建全局配置实例
settings = Settings()


def validate_settings() -> None:
    """
    验证配置安全性（启动时调用）

    检查项：
    1. SECRET_KEY 必须设置且长度不低于 32 字符
    2. WEB_PANEL_PASSWORD 必须设置

    Raises:
        ValueError: 配置不合法时抛出异常阻止启动
    """
    if not settings.secret_key or len(settings.secret_key) < 32:
        raise ValueError(
            "SECRET_KEY 未设置或长度不足32字符。"
            "请在 .env 中设置有效的 SECRET_KEY（不低于32字符）"
        )

    if not settings.web_panel_password:
        raise ValueError(
            "WEB_PANEL_PASSWORD 未设置。"
            "请在 .env 中设置有效的 Web 面板密码"
        )


def get_settings() -> Settings:
    """获取配置实例"""
    return settings