# -*- coding: utf-8 -*-
"""
数据模型模块
定义所有数据结构和数据库模型
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """数据库基类"""
    pass


# ========== 枚举类型 ==========


class ArticleSource(str, Enum):
    """资讯来源类型"""
    RSS = "rss"
    CUSTOM = "custom"


class RSSSourceType(str, Enum):
    """RSS源类型"""
    STANDARD = "standard"      # 标准RSS源
    RSSHUB = "rsshub"         # RSSHub生成的源
    AUTO = "auto"              # 自动发现模式


class ArticleStatus(str, Enum):
    """资讯状态"""
    PENDING = "pending"       # 待处理
    PROCESSED = "processed"   # 已处理(摘要/评分完成)
    PUBLISHED = "published"  # 已推送
    ARCHIVED = "archived"    # 已归档


class TimeRange(str, Enum):
    """时间范围"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class WebhookPlatform(str, Enum):
    """Webhook 平台类型"""
    WECOM = "wecom"
    GIT = "git"                    # Git 同步模式（支持 GitHub、Gitee）
    OBSIDIAN_LOCAL = "obsidian_local"  # Obsidian Local REST API 本地模式
    # 兼容旧名称
    OBSIDIAN_GIT = "obsidian_git"  # 已废弃，使用 GIT


class LLMProvider(str, Enum):
    """LLM 提供商"""
    ZHIPU = "ZHIPU"
    SILICONFLOW = "SILICONFLOW"
    OPENROUTER = "OPENROUTER"
    MODELSCOPE = "MODELSCOPE"


class EmbeddingProvider(str, Enum):
    """Embedding 模型提供商"""
    OLLAMA = "ollama"
    OPENAI = "openai"
    SILICONFLOW = "siliconflow"
    OPENROUTER = "openrouter"


class VectorDBType(str, Enum):
    """向量数据库类型"""
    CHROMADB = "chromadb"
    MILVUS = "milvus"
    QDRANT = "qdrant"


class TaskType(str, Enum):
    """定时任务类型"""
    FIXED = "fixed"      # 每日/每周固定时间
    INTERVAL = "interval"  # 间隔触发


# ========== 日志相关枚举 ==========


class LogType(str, Enum):
    """日志类型"""
    CONFIG_CHANGE = "config_change"  # 配置变更
    TASK_EXEC = "task_exec"          # 任务执行
    SYSTEM = "system"               # 系统


class LogLevel(str, Enum):
    """日志级别"""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class LogAction(str, Enum):
    """操作动作"""
    # 配置变更
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    RELOAD = "reload"
    # 任务执行
    START = "start"
    SUCCESS = "success"
    FAIL = "fail"


# ========== 数据模型 ==========


class Article(Base):
    """
    资讯文章模型

    存储从各来源采集的AI资讯文章

    状态流转：pending -> processed -> published/archived
    """
    __tablename__ = "articles"

    # 主键
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, doc="主键ID")

    # 唯一标识 (URL哈希)
    url_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, doc="URL哈希值，用于去重")
    
    # 基本信息
    title: Mapped[str] = mapped_column(String(500), nullable=False, doc="文章标题")
    url: Mapped[str] = mapped_column(String(1000), nullable=False, doc="原文链接")
    source: Mapped[str] = mapped_column(String(50), nullable=False, doc="来源类型：rss/custom")
    source_name: Mapped[str] = mapped_column(String(100), doc="来源名称，如OpenAI Blog")

    # 内容
    summary: Mapped[Optional[str]] = mapped_column(Text, doc="LLM生成的摘要")
    content: Mapped[Optional[str]] = mapped_column(Text, doc="原始内容（可能被截断）")
    author: Mapped[Optional[str]] = mapped_column(String(200), doc="作者")
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, doc="发布时间")

    # AI处理结果
    tags: Mapped[Optional[str]] = mapped_column(String(500), doc="标签，逗号分隔，如 #LLM,#Robotics")
    score: Mapped[Optional[float]] = mapped_column(Float, doc="价值评分 0-10")
    keywords: Mapped[Optional[str]] = mapped_column(String(500), doc="关键词")

    # 状态
    status: Mapped[str] = mapped_column(
        String(20),
        default=ArticleStatus.PENDING.value,
        index=True,
        doc="状态：pending/processed/published/archived"
    )
    is_pushed: Mapped[bool] = mapped_column(Boolean, default=False, doc="是否已推送（日报/周报）")
    is_pushed_immediate: Mapped[bool] = mapped_column(Boolean, default=False, doc="是否已即时推送（高分推送）")
    pushed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, doc="推送时间")

    # 向量与缓存相关
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False, doc="是否命中缓存")
    cache_source_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("articles.id", ondelete="SET NULL"),
        nullable=True,
        doc="缓存来源文章ID"
    )
    has_vector: Mapped[bool] = mapped_column(Boolean, default=False, doc="是否已有向量embedding")

    # 元数据
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        doc="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        doc="更新时间"
    )
    
    # 索引
    __table_args__ = (
        Index("idx_article_status_published", "status", "published_at"),
        Index("idx_article_source_status", "source", "status"),
        Index("idx_article_has_vector", "has_vector"),
        Index("idx_article_cache_hit", "cache_hit"),
    )
    
    def __repr__(self):
        return f"<Article(id={self.id}, title='{self.title[:30]}...', score={self.score})>"


class GitHubRepo(Base):
    """
    GitHub热门项目模型

    存储从GitHub Trending采集的项目信息
    """
    __tablename__ = "github_repos"

    # 主键
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, doc="主键ID")

    # 唯一标识
    repo_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, doc="仓库哈希（去重）")

    # 基本信息
    full_name: Mapped[str] = mapped_column(String(200), nullable=False, doc="仓库全名，如 octocat/hello-world")
    description: Mapped[Optional[str]] = mapped_column(String(1000), doc="项目描述")
    url: Mapped[str] = mapped_column(String(500), nullable=False, doc="仓库URL")
    language: Mapped[Optional[str]] = mapped_column(String(50), doc="编程语言")

    # 统计数据
    stars: Mapped[int] = mapped_column(Integer, default=0, doc="Star数量")
    forks: Mapped[int] = mapped_column(Integer, default=0, doc="Fork数量")
    stars_today: Mapped[int] = mapped_column(Integer, default=0, doc="今日新增Star数量")

    # AI处理结果
    summary: Mapped[Optional[str]] = mapped_column(Text, doc="LLM生成的项目简介")
    tags: Mapped[Optional[str]] = mapped_column(String(500), doc="标签，逗号分隔")
    score: Mapped[Optional[float]] = mapped_column(Float, doc="价值评分 0-10")
    keywords: Mapped[Optional[str]] = mapped_column(String(500), doc="关键词")

    # 采集信息
    trending_date: Mapped[datetime] = mapped_column(DateTime, doc="采集日期")
    trending_range: Mapped[str] = mapped_column(String(20), doc="采集范围：daily/weekly/monthly")

    # 状态
    status: Mapped[str] = mapped_column(String(20), default=ArticleStatus.PENDING.value, doc="状态：pending/processed/published")
    is_pushed: Mapped[bool] = mapped_column(Boolean, default=False, doc="是否已推送")
    pushed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, doc="推送时间")

    # 元数据
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), doc="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        doc="更新时间"
    )
    
    __table_args__ = (
        Index("idx_github_date_range", "trending_date", "trending_range"),
        Index("idx_github_language", "language"),
    )
    
    def __repr__(self):
        return f"<GitHubRepo(id={self.id}, name='{self.full_name}', stars={self.stars})>"


class User(Base):
    """
    用户模型

    存储用户信息和订阅设置
    支持 Web 面板用户和消息推送用户分离
    """
    __tablename__ = "users"

    # 主键
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, doc="主键ID")

    # 用户标识
    # - Web 面板用户：platform='web_panel'，platform_id 存储用户名
    # - 消息推送用户：platform='wecom/telegram'，platform_id 存储平台用户 ID
    platform: Mapped[str] = mapped_column(String(20), nullable=False, default="wecom", doc="平台类型：wecom/web_panel")
    platform_id: Mapped[str] = mapped_column(String(100), nullable=False, doc="平台用户ID")

    # Web 面板用户专有字段
    is_web_panel_user: Mapped[bool] = mapped_column(Boolean, default=False, doc="是否为Web面板用户")
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), doc="密码哈希（bcrypt）")

    # 用户信息
    name: Mapped[Optional[str]] = mapped_column(String(100), doc="用户名称")

    # 订阅设置 (消息推送用户用)
    subscribed_topics: Mapped[Optional[str]] = mapped_column(String(500), doc="订阅话题，逗号分隔")
    preferred_languages: Mapped[Optional[str]] = mapped_column(String(200), doc="偏好的GitHub编程语言")
    push_enabled: Mapped[bool] = mapped_column(Boolean, default=True, doc="是否启用推送")

    # 通知时间设置 (消息推送用户用)
    daily_report_time: Mapped[Optional[str]] = mapped_column(String(10), doc="日报推送时间，如 08:00")
    weekly_report_time: Mapped[Optional[str]] = mapped_column(String(10), doc="周报推送时间，如 09:00")
    weekly_report_day: Mapped[int] = mapped_column(Integer, default=0, doc="周报推送星期，0=周一")

    # 状态
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, doc="是否激活")

    # 元数据
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), doc="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        doc="更新时间"
    )
    
    __table_args__ = (
        Index("idx_user_platform", "platform", "platform_id", unique=True),
        Index("idx_user_is_web_panel", "is_web_panel_user"),
    )
    
    def __repr__(self):
        return f"<User(id={self.id}, platform='{self.platform}', name='{self.name}')>"


class RSSSource(Base):
    """
    RSS订阅源模型

    存储用户自定义的RSS订阅源
    """
    __tablename__ = "rss_sources"

    # 主键
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, doc="主键ID")

    # 源信息
    name: Mapped[str] = mapped_column(String(100), nullable=False, doc="RSS源名称")
    url: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True, doc="RSS源URL")
    category: Mapped[Optional[str]] = mapped_column(String(50), doc="分类：ai/tech/github")
    source_type: Mapped[str] = mapped_column(
        String(20),
        default=RSSSourceType.STANDARD.value,
        nullable=False,
        doc="源类型：standard/rsshub/builtin"
    )

    # 采集设置
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, doc="是否启用")
    rsshub_unavailable: Mapped[bool] = mapped_column(
        Boolean, default=False,
        doc="RSSHub不可用标记，防止用户在RSSHub停用时启用该源"
    )
    fetch_interval: Mapped[int] = mapped_column(Integer, default=60, doc="采集间隔（分钟）")

    # 错误计数 (用于判断是否需要禁用)
    fetch_error_count: Mapped[int] = mapped_column(Integer, default=0, doc="采集错误次数")

    # 元数据
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), doc="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        doc="更新时间"
    )

    # 统计
    last_fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), doc="最后采集时间")
    article_count: Mapped[int] = mapped_column(Integer, default=0, doc="已采集文章数")

    # 增量检测字段（Last-Modified/ETag）
    last_modified: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, doc="Last-Modified头")
    etag: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, doc="ETag头")

    __table_args__ = (
        Index("idx_rss_url", "url", unique=True),
        Index("idx_rss_is_active", "is_active"),
    )
    
    def __repr__(self):
        return f"<RSSSource(id={self.id}, name='{self.name}', url='{self.url}')>"


class GitHubLanguage(Base):
    """
    GitHub采集语言配置模型

    存储用户配置的GitHub热门项目采集语言
    """
    __tablename__ = "github_languages"

    # 主键
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, doc="主键ID")

    # 语言标识（GitHub官方语言名称）
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, doc="语言名称（如 Python）")

    # GitHub官方颜色代码（如 "#3572A5" for Python）
    color: Mapped[Optional[str]] = mapped_column(String(7), doc="GitHub官方颜色代码")

    # 是否启用采集
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, doc="是否启用采集")

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), doc="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        doc="更新时间"
    )

    __table_args__ = (
        Index("idx_github_lang_active", "is_active"),
    )

    def __repr__(self):
        return f"<GitHubLanguage(id={self.id}, name='{self.name}')>"


class PushLog(Base):
    """
    推送日志模型

    记录所有推送历史
    """
    __tablename__ = "push_logs"

    # 主键
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, doc="主键ID")

    # 关联
    webhook_config_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("webhook_configs.id"),
        nullable=True,
        index=True,
        doc="Webhook配置ID"
    )
    webhook_config_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        doc="Webhook配置名称（冗余字段，防止 webhook 删除后丢失上下文）"
    )
    article_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("articles.id"),
        nullable=True,
        doc="文章ID（可为空）"
    )
    github_repo_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("github_repos.id"),
        nullable=True,
        doc="GitHub项目ID（可为空）"
    )

    # 推送信息
    platform: Mapped[str] = mapped_column(String(20), doc="推送平台：wecom/telegram/obsidian")
    push_type: Mapped[str] = mapped_column(String(20), doc="推送类型：immediate/daily/weekly")
    content: Mapped[Text] = mapped_column(Text, doc="推送内容")

    # 状态
    is_success: Mapped[bool] = mapped_column(Boolean, default=True, doc="是否成功")
    error_message: Mapped[Optional[str]] = mapped_column(Text, doc="错误信息")

    # === Obsidian/Git 相关字段 ===
    obsidian_file_path: Mapped[Optional[str]] = mapped_column(String(500), doc="Obsidian文件路径")
    git_commit_sha: Mapped[Optional[str]] = mapped_column(String(40), doc="Git提交SHA（远程模式）")
    http_status_code: Mapped[Optional[int]] = mapped_column(Integer, doc="HTTP响应码（本地模式）")

    # 时间
    pushed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), doc="推送时间")

    def __repr__(self):
        return f"<PushLog(id={self.id}, webhook_id={self.webhook_config_id}, type='{self.push_type}')>"


# ========== Web 面板新增模型 ==========


class WebhookConfig(Base):
    """
    Webhook 配置模型

    存储 Webhook 配置信息，支持企业微信/Obsidian 等平台

    字段变更历史：
    - 2024-04 新增：推送相关字段
    - 2026-04-22 重构：拆分到 PushSettings/FailureConfig 表
                   保留 core 字段：name, platform, webhook_key
                   推送配置通过 push_settings 关系访问
                   失败配置通过 failure_config 关系访问

    迁移说明：
    - push_immediate_enabled, push_daily_enabled, push_weekly_enabled -> PushSettings
    - push_immediate_threshold, push_daily_threshold, push_weekly_threshold -> PushSettings
    - push_daily_limit, push_weekly_limit -> PushSettings
    - push_fail_count, push_fail_threshold, is_disabled -> FailureConfig
    """
    __tablename__ = "webhook_configs"

    # 主键
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, doc="主键ID")

    # 配置信息
    name: Mapped[str] = mapped_column(String(100), nullable=False, doc="配置名称")
    platform: Mapped[str] = mapped_column(String(20), nullable=False, doc="平台类型：wecom/git/obsidian_local")

    # Webhook 密钥 (AES-256-GCM 加密存储)
    webhook_key: Mapped[str] = mapped_column(String(255), nullable=False, doc="Webhook密钥")

    # === 原有字段（保留兼容 - 即将废弃） ===
    push_threshold: Mapped[float] = mapped_column(Float, default=85.0, doc="推送阈值（已废弃，请使用 PushSettings）")
    push_enabled: Mapped[bool] = mapped_column(Boolean, default=True, doc="是否启用推送（已废弃）")

    # 状态
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, doc="是否启用")

    # 元数据
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), doc="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        doc="更新时间"
    )

    # === 关联关系 ===
    # 推送设置（推送类型开关、阈值、数量限制）
    push_settings: Mapped["PushSettings"] = relationship(
        "PushSettings",
        back_populates="webhook_config",
        uselist=False,
        cascade="all, delete-orphan"
    )
    # 失败处理配置
    failure_config: Mapped["FailureConfig"] = relationship(
        "FailureConfig",
        back_populates="webhook_config",
        uselist=False,
        cascade="all, delete-orphan"
    )
    # 模板配置（一个 webhook 可有多个模板：daily/weekly/immediate）
    templates: Mapped[List["WebhookTemplate"]] = relationship(
        "WebhookTemplate",
        back_populates="webhook_config",
        cascade="all, delete-orphan"
    )
    # Obsidian 本地模式配置
    obsidian_config: Mapped[Optional["ObsidianConfig"]] = relationship(
        "ObsidianConfig",
        back_populates="webhook_config",
        uselist=False,
        cascade="all, delete-orphan"
    )
    # Git 远程模式配置
    git_repo_config: Mapped[Optional["GitRepoConfig"]] = relationship(
        "GitRepoConfig",
        back_populates="webhook_config",
        uselist=False,
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_webhook_platform", "platform"),
        Index("idx_webhook_is_active", "is_active"),
    )

    @property
    def decrypted_key(self) -> str:
        """
        获取解密后的 Webhook 密钥

        统一在模型层处理密钥解密，避免在多处重复调用 decrypt_api_key

        Returns:
            str: 解密后的密钥，如果解密失败则返回原文
        """
        from app.utils.crypto import decrypt_api_key
        try:
            return decrypt_api_key(self.webhook_key, raise_on_error=False)
        except Exception:
            return self.webhook_key

    def __repr__(self):
        return f"<WebhookConfig(id={self.id}, name='{self.name}', platform='{self.platform}')>"


class PushSettings(Base):
    """
    推送设置模型

    从 WebhookConfig 拆分出来，存储推送类型相关的独立配置
    支持按推送类型（immediate/daily/weekly）设置开关和阈值

    关联关系：
    - 每个 WebhookConfig 有一个 PushSettings
    - PushSettings.webhook_config_id -> WebhookConfig.id
    """
    __tablename__ = "push_settings"

    # 主键
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, doc="主键ID")

    # 外键关联
    webhook_config_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("webhook_configs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        doc="Webhook配置ID"
    )

    # === 推送类型开关 ===
    push_immediate_enabled: Mapped[bool] = mapped_column(Boolean, default=True, doc="高分推送开关")
    push_daily_enabled: Mapped[bool] = mapped_column(Boolean, default=True, doc="日报推送开关")
    push_weekly_enabled: Mapped[bool] = mapped_column(Boolean, default=True, doc="周报推送开关")

    # === 推送类型阈值 ===
    push_immediate_threshold: Mapped[float] = mapped_column(Float, default=85.0, doc="高分推送阈值（0-100）")
    push_daily_threshold: Mapped[float] = mapped_column(Float, default=75.0, doc="日报推送阈值（0-100）")
    push_weekly_threshold: Mapped[float] = mapped_column(Float, default=80.0, doc="周报推送阈值（0-100）")

    # === 推送数量限制 ===
    push_daily_limit: Mapped[int] = mapped_column(Integer, default=30, doc="日报推送数量限制")
    push_weekly_limit: Mapped[int] = mapped_column(Integer, default=60, doc="周报推送数量限制")

    # 元数据
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), doc="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        doc="更新时间"
    )

    # === 关联关系 ===
    webhook_config: Mapped["WebhookConfig"] = relationship(
        "WebhookConfig",
        back_populates="push_settings"
    )

    __table_args__ = (
        Index("idx_push_settings_webhook_id", "webhook_config_id", unique=True),
    )

    def __repr__(self):
        return f"<PushSettings(id={self.id}, webhook_config_id={self.webhook_config_id})>"


class FailureConfig(Base):
    """
    失败处理配置模型

    从 WebhookConfig 拆分出来，存储推送失败处理相关的配置

    关联关系：
    - 每个 WebhookConfig 有一个 FailureConfig
    - FailureConfig.webhook_config_id -> WebhookConfig.id
    """
    __tablename__ = "failure_configs"

    # 主键
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, doc="主键ID")

    # 外键关联
    webhook_config_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("webhook_configs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        doc="Webhook配置ID"
    )

    # === 失败处理配置 ===
    push_fail_count: Mapped[int] = mapped_column(Integer, default=0, doc="推送失败次数")
    push_fail_threshold: Mapped[int] = mapped_column(Integer, default=10, doc="失败次数阈值")
    is_disabled: Mapped[bool] = mapped_column(Boolean, default=False, doc="是否因失败过多被停用")

    # 元数据
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), doc="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        doc="更新时间"
    )

    # === 关联关系 ===
    webhook_config: Mapped["WebhookConfig"] = relationship(
        "WebhookConfig",
        back_populates="failure_config"
    )

    __table_args__ = (
        Index("idx_failure_config_webhook_id", "webhook_config_id", unique=True),
    )

    def __repr__(self):
        return f"<FailureConfig(id={self.id}, webhook_config_id={self.webhook_config_id}, fail_count={self.push_fail_count})>"


class LLMModel(Base):
    """
    LLM 模型配置模型

    存储 LLM 模型的配置信息，支持多平台模型注册
    """
    __tablename__ = "llm_models"

    # 主键
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, doc="主键ID")

    # 模型信息
    provider: Mapped[str] = mapped_column(String(20), nullable=False, doc="提供商：ZHIPU/SILICONFLOW/OPENROUTER/MODELSCOPE")
    model_name: Mapped[str] = mapped_column(String(100), nullable=False, doc="模型名称")

    # API 配置 (API 密钥加密存储)
    api_key: Mapped[str] = mapped_column(String(255), nullable=False, doc="API密钥")
    api_base: Mapped[Optional[str]] = mapped_column(String(500), doc="API地址")

    # 模型能力
    can_disable_thinking: Mapped[bool] = mapped_column(Boolean, default=False, doc="是否可关闭思考模式")
    can_use_tool: Mapped[bool] = mapped_column(Boolean, default=False, doc="是否支持工具调用")

    # 并发控制
    max_concurrent: Mapped[int] = mapped_column(Integer, default=1, doc="最大并发数")

    # 状态
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, doc="是否启用（参与轮询）")
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, doc="连续失败次数")

    # 元数据
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), doc="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        doc="更新时间"
    )
    
    __table_args__ = (
        Index("idx_llm_provider_model", "provider", "model_name", unique=True),
        Index("idx_llm_is_active", "is_active"),
    )
    
    def __repr__(self):
        return f"<LLMModel(id={self.id}, provider='{self.provider}', model_name='{self.model_name}')>"


class ScheduledTaskConfig(Base):
    """
    定时任务配置模型

    存储定时任务的配置信息，支持热重载
    """
    __tablename__ = "scheduled_task_configs"

    # 主键
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, doc="主键ID")

    # 任务信息
    task_name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, doc="任务名称")
    task_type: Mapped[str] = mapped_column(String(20), nullable=False, doc="任务类型：fixed/interval")

    # 固定时间触发配置 (task_type=fixed 时使用)
    hour: Mapped[Optional[int]] = mapped_column(Integer, doc="小时 0-23")
    minute: Mapped[Optional[int]] = mapped_column(Integer, doc="分钟 0-59")
    day_of_week: Mapped[Optional[int]] = mapped_column(Integer, doc="星期几 0=周一")

    # 间隔触发配置 (task_type=interval 时使用)
    interval_minutes: Mapped[Optional[int]] = mapped_column(Integer, doc="间隔分钟数")

    # 状态
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, doc="是否启用")

    # 配置版本号 (用于热重载检测)
    config_version: Mapped[int] = mapped_column(Integer, default=1, doc="配置版本号")

    # 元数据
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), doc="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        doc="更新时间"
    )
    
    __table_args__ = (
        Index("idx_task_task_name", "task_name", unique=True),
        Index("idx_task_is_active", "is_active"),
    )
    
    def __repr__(self):
        return f"<ScheduledTaskConfig(id={self.id}, task_name='{self.task_name}', task_type='{self.task_type}')>"


class OperationLog(Base):
    """
    操作日志模型

    用于记录操作审计日志：
    - 定时任务配置的增删改（CONFIG_CHANGE）
    - 定时任务的执行开始/成功/失败（TASK_EXEC）
    - 系统级别的操作（SYSTEM）
    """
    __tablename__ = "operation_logs"

    # 主键
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, doc="主键ID")

    # 日志分类
    log_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        doc="日志类型：config_change/task_exec/system"
    )
    log_level: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default=LogLevel.INFO.value,
        doc="日志级别：INFO/WARNING/ERROR"
    )

    # 关联资源
    task_name: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        doc="关联任务名称，如 fetch_ai_news"
    )

    # 操作信息
    operator: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        doc="操作者：web_panel/system/api/scheduler"
    )
    action: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="操作类型：create/update/delete/reload/start/success/fail"
    )

    # 详情（JSON 格式存储）
    detail: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="详细信息，JSON格式，如 {\"duration_ms\": 1523, \"articles_count\": 12}"
    )

    # 客户端信息
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        doc="客户端IP地址"
    )

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
        doc="创建时间"
    )

    # 复合索引
    __table_args__ = (
        Index("idx_op_type_created", "log_type", "created_at"),
        Index("idx_op_task_created", "task_name", "created_at"),
    )

    def __repr__(self):
        return f"<OperationLog(id={self.id}, type={self.log_type}, action={self.action})>"


class TaskExecutionStatus(str, Enum):
    """任务执行状态枚举"""
    START = "start"
    SUCCESS = "success"
    FAIL = "fail"
    TIMEOUT = "timeout"


class TemplateType(str, Enum):
    """模板类型枚举"""
    DAILY = "daily"      # 日报模板
    WEEKLY = "weekly"    # 周报模板
    IMMEDIATE = "immediate"  # 高分推送模板


class TaskExecutionHistory(Base):
    """
    任务执行历史记录模型

    用于追踪每个任务的每次执行详情，支持：
    - 执行时间统计
    - 成功率分析
    - 性能监控
    - 异常模式发现
    """
    __tablename__ = "task_execution_history"

    # 主键
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, doc="主键ID")

    # 任务标识
    task_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True, doc="任务名称")

    # 执行状态
    status: Mapped[str] = mapped_column(String(20), nullable=False, doc="执行状态：start/success/fail/timeout")

    # 时间信息
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, doc="开始时间")
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, doc="结束时间")

    # 执行结果
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, doc="执行时长（毫秒）")
    result: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, doc="执行结果摘要")
    error_message: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True, doc="错误信息")

    # 元数据
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        doc="创建时间"
    )

    # 索引
    __table_args__ = (
        Index("idx_task_history_name_start", "task_name", "start_time"),
    )

    def __repr__(self):
        return f"<TaskExecutionHistory(id={self.id}, task_name='{self.task_name}', status='{self.status}')>"


class WebhookTemplate(Base):
    """
    Webhook 模板模型

    存储每个 Webhook 的自定义模板配置，支持日报/周报/高分推送三种模板

    关联关系：
    - 每个 WebhookConfig 可有多个 WebhookTemplate（每种类型一个）
    - 通过 template_type 区分模板类型（daily/weekly/immediate）
    """
    __tablename__ = "webhook_templates"

    # 主键
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, doc="主键ID")

    # 外键关联
    webhook_config_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("webhook_configs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Webhook配置ID"
    )

    # 模板信息
    template_type: Mapped[str] = mapped_column(String(20), nullable=False, doc="模板类型：daily/weekly/immediate")
    template_name: Mapped[str] = mapped_column(String(100), nullable=False, doc="模板名称")
    template_content: Mapped[str] = mapped_column(Text, nullable=False, default="", doc="模板内容")

    # 状态
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, doc="是否启用")

    # 元数据
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), doc="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        doc="更新时间"
    )

    # === 关联关系 ===
    webhook_config: Mapped["WebhookConfig"] = relationship(
        "WebhookConfig",
        back_populates="templates"
    )

    __table_args__ = (
        # 每个 webhook 每种类型只能有一个模板
        Index("idx_template_webhook_type", "webhook_config_id", "template_type", unique=True),
        Index("idx_template_is_active", "is_active"),
    )

    def __repr__(self):
        return f"<WebhookTemplate(id={self.id}, webhook_id={self.webhook_config_id}, type='{self.template_type}')>"


class ObsidianConfig(Base):
    """
    Obsidian 本地模式配置模型

    存储 Obsidian Local REST API 的连接配置

    关联关系：
    - 每个 WebhookConfig 有一个 ObsidianConfig
    - 通过 push_mode='local' 区分本地/远程模式
    """
    __tablename__ = "obsidian_configs"

    # 主键
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, doc="主键ID")

    # 外键关联
    webhook_config_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("webhook_configs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        doc="Webhook配置ID"
    )

    # API 配置
    api_url: Mapped[str] = mapped_column(String(500), nullable=False, doc="Obsidian Local REST API地址")
    api_key: Mapped[str] = mapped_column(String(255), nullable=False, doc="API密钥（AES加密存储）")
    vault_path: Mapped[str] = mapped_column(String(500), nullable=False, doc="Vault根目录")

    # 文件夹配置
    daily_folder: Mapped[str] = mapped_column(String(200), nullable=False, default="AI-News/Daily", doc="日报文件夹")
    weekly_folder: Mapped[str] = mapped_column(String(200), nullable=False, default="AI-News/Weekly", doc="周报文件夹")
    immediate_folder: Mapped[str] = mapped_column(String(200), nullable=False, default="AI-News/Immediate", doc="高分推送文件夹")

    # SSL 配置
    verify_ssl: Mapped[bool] = mapped_column(Boolean, default=True, doc="是否验证SSL")

    # 元数据
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), doc="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        doc="更新时间"
    )

    # === 关联关系 ===
    webhook_config: Mapped["WebhookConfig"] = relationship(
        "WebhookConfig",
        back_populates="obsidian_config"
    )

    __table_args__ = (
        Index("idx_obsidian_webhook_id", "webhook_config_id", unique=True),
    )

    def __repr__(self):
        return f"<ObsidianConfig(id={self.id}, webhook_id={self.webhook_config_id}, vault='{self.vault_path}')>"


class GitRepoConfig(Base):
    """
    Git 远程模式配置模型

    存储 Git 仓库的连接配置，支持 GitHub/Gitee 等平台

    关联关系：
    - 每个 WebhookConfig 有一个 GitRepoConfig
    - 通过 push_mode='git' 区分本地/远程模式
    """
    __tablename__ = "git_repo_configs"

    # 主键
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, doc="主键ID")

    # 外键关联
    webhook_config_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("webhook_configs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        doc="Webhook配置ID"
    )

    # Git 仓库配置
    repo_url: Mapped[str] = mapped_column(String(500), nullable=False, doc="Git仓库地址")
    branch: Mapped[str] = mapped_column(String(100), nullable=False, default="main", doc="分支名")

    # 认证配置
    access_token: Mapped[str] = mapped_column(String(255), nullable=False, doc="访问令牌（AES加密存储）")
    credential_type: Mapped[str] = mapped_column(String(20), nullable=False, default="deploy_token", doc="凭证类型：deploy_token/pat")

    # 提交者信息
    author_name: Mapped[str] = mapped_column(String(100), nullable=False, default="AI News Bot", doc="提交者名称")
    author_email: Mapped[Optional[str]] = mapped_column(String(100), doc="提交者邮箱")

    # 文件夹配置
    daily_folder: Mapped[str] = mapped_column(String(200), nullable=False, default="Daily", doc="日报文件夹")
    weekly_folder: Mapped[str] = mapped_column(String(200), nullable=False, default="Weekly", doc="周报文件夹")
    immediate_folder: Mapped[str] = mapped_column(String(200), nullable=False, default="Immediate", doc="高分推送文件夹")

    # 元数据
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), doc="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        doc="更新时间"
    )

    # === 关联关系 ===
    webhook_config: Mapped["WebhookConfig"] = relationship(
        "WebhookConfig",
        back_populates="git_repo_config"
    )

    __table_args__ = (
        Index("idx_git_repo_webhook_id", "webhook_config_id", unique=True),
    )

    def __repr__(self):
        return f"<GitRepoConfig(id={self.id}, webhook_id={self.webhook_config_id}, repo='{self.repo_url}')>"


class VaultFile(Base):
    """
    Vault 文件追踪模型

    用于记录已推送的文件，实现去重功能

    关联关系：
    - 通过 webhook_id 关联 WebhookConfig
    """
    __tablename__ = "vault_files"

    # 主键
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, doc="主键ID")

    # 外键关联
    webhook_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("webhook_configs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Webhook配置ID"
    )

    # 文件信息
    file_path: Mapped[str] = mapped_column(String(500), nullable=False, doc="文件路径（相对Vault）")
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, doc="内容哈希（去重用）")

    # 推送类型
    push_type: Mapped[str] = mapped_column(String(20), nullable=False, doc="推送类型：daily/weekly/immediate")

    # 元数据
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), doc="创建时间")

    __table_args__ = (
        Index("idx_vault_file_webhook_path", "webhook_id", "file_path"),
        Index("idx_vault_file_hash", "file_hash"),
    )

    def __repr__(self):
        return f"<VaultFile(id={self.id}, webhook_id={self.webhook_id}, path='{self.file_path}')>"


class DynamicSkipDomain(Base):
    """
    动态跳过域名表

    用于记录域名补全失败次数，当连续失败达到阈值时自动跳过该域名

    关联关系：
    - 通过 domain 字段唯一标识一个域名
    """
    __tablename__ = "dynamic_skip_domains"

    # 主键
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, doc="主键ID")

    # 域名（唯一索引）
    domain: Mapped[str] = mapped_column(String(255), unique=True, index=True, doc="域名")

    # 失败统计
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, doc="连续失败次数")
    total_failures: Mapped[int] = mapped_column(Integer, default=0, doc="总失败次数")
    total_success: Mapped[int] = mapped_column(Integer, default=0, doc="总成功次数")

    # 状态
    is_skip: Mapped[bool] = mapped_column(Boolean, default=False, doc="是否被跳过")
    skip_reason: Mapped[Optional[str]] = mapped_column(String(100), doc="跳过原因")

    # 时间戳
    last_failure_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), doc="最后失败时间")
    skip_since: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), doc="跳过开始时间")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), doc="创建时间")

    # 索引
    __table_args__ = (
        Index("idx_skip_domain", "domain"),
        Index("idx_skip_is_skip", "is_skip"),
    )

    def __repr__(self):
        return f"<DynamicSkipDomain(id={self.id}, domain='{self.domain}', is_skip={self.is_skip})>"


class RSSHubRoute(Base):
    """
    RSSHub 路由表

    存储从 RSSHub routes.json 解析的路由信息
    支持增量同步和软删除

    关联关系：
    - 通过 route_path 字段唯一标识一条路由
    - 通过 removed_at 字段实现软删除
    """
    __tablename__ = "rsshub_routes"

    # 主键
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, doc="主键ID")

    # ===== 路由标识 =====
    route_path: Mapped[str] = mapped_column(String(500), nullable=False, doc="路由路径")
    route_name: Mapped[Optional[str]] = mapped_column(String(200), doc="路由名称")
    namespace_id: Mapped[str] = mapped_column(String(50), nullable=False, doc="命名空间ID（复合唯一键组成部分）")
    domain: Mapped[str] = mapped_column(String(200), nullable=False, doc="域名（如 twitter.com）")
    example_path: Mapped[Optional[str]] = mapped_column(String(500), doc="示例路径")

    # ===== 元数据 =====
    category: Mapped[Optional[str]] = mapped_column(String(50), doc="主分类")
    categories: Mapped[Optional[str]] = mapped_column(Text, doc="分类列表（JSON数组）")
    lang: Mapped[str] = mapped_column(String(10), default="zh-CN", doc="语言")
    has_params: Mapped[bool] = mapped_column(Boolean, default=False, doc="是否有路径参数")
    description: Mapped[Optional[str]] = mapped_column(Text, doc="路由描述")

    # ===== 维护信息 =====
    maintainers: Mapped[Optional[str]] = mapped_column(Text, doc="维护者列表（JSON数组）")
    features: Mapped[Optional[str]] = mapped_column(Text, doc="特性（JSON对象）")
    source_file: Mapped[str] = mapped_column(String(100), default="routes.json", doc="来源文件")

    # ===== 生命周期 =====
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, doc="是否激活")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), doc="首次出现时间")
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        doc="最后更新时间"
    )
    removed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, doc="软删除时间")

    # 索引
    __table_args__ = (
        UniqueConstraint("namespace_id", "route_path", name="uq_rsshub_route_ns_path"),
        Index("idx_routes_category", "category"),
        Index("idx_routes_domain", "domain"),
        Index("idx_routes_namespace", "namespace_id"),
        Index("idx_routes_lang", "lang"),
        Index("idx_routes_active", "is_active"),
    )

    def __repr__(self):
        return f"<RSSHubRoute(id={self.id}, route_path='{self.route_path[:50]}...')>"


# ========== 向量数据库相关模型（Phase 1）==========


class EmbeddingModel(Base):
    """
    Embedding 模型配置模型

    存储 Embedding 模型的配置信息，支持多平台模型注册
    设计模式参考 LLMModel
    """
    __tablename__ = "embedding_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, doc="主键ID")
    provider: Mapped[str] = mapped_column(String(20), nullable=False, doc="提供商")
    model_name: Mapped[str] = mapped_column(String(100), nullable=False, doc="模型名称")
    display_name: Mapped[Optional[str]] = mapped_column(String(100), doc="显示名称")

    api_key: Mapped[str] = mapped_column(String(255), nullable=False, doc="API密钥")
    api_base: Mapped[Optional[str]] = mapped_column(String(500), doc="API地址")

    dimension: Mapped[int] = mapped_column(Integer, default=768, doc="向量维度")
    max_batch_size: Mapped[int] = mapped_column(Integer, default=20, doc="最大批处理大小")

    max_concurrency: Mapped[int] = mapped_column(Integer, default=3, doc="最大并发数")
    priority: Mapped[int] = mapped_column(Integer, default=10, doc="优先级")

    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, doc="是否启用")
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, doc="连续失败次数")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), doc="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        doc="更新时间"
    )

    __table_args__ = (
        Index("idx_emb_provider_model", "provider", "model_name", unique=True),
        Index("idx_emb_is_enabled", "is_enabled"),
    )

    def __repr__(self):
        return f"<EmbeddingModel(id={self.id}, provider='{self.provider}', model='{self.model_name}')>"


class VectorDBConfig(Base):
    """
    向量数据库配置模型

    存储向量数据库的连接配置，支持多后端切换。
    支持同一数据库实例下不同维度（dimension）的 collection 配置，
    通过 db_type + connection_string + dimension 联合唯一约束避免重复。
    """
    __tablename__ = "vector_db_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, doc="主键ID")
    db_type: Mapped[str] = mapped_column(String(20), nullable=False, default="chromadb", doc="数据库类型：chromadb/milvus/qdrant")
    connection_string: Mapped[str] = mapped_column(String(500), default="storage/chromadb", doc="连接字符串")
    collection_prefix: Mapped[str] = mapped_column(
        String(50),
        default="ai_news_bot",
        doc="collection命名前缀（仅供get_collection_name使用，不再在API中暴露）",
    )
    dimension: Mapped[int] = mapped_column(
        Integer,
        default=1024,
        doc="向量维度。创建collection时必须指定。不同维度的向量无法共存于同一collection。",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, doc="是否激活")
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        doc="是否为默认兜底配置。默认配置不支持删除，用于确保向量功能始终有可用配置。",
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), doc="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        doc="更新时间"
    )

    __table_args__ = (
        Index("idx_vecdb_is_active", "is_active"),
        Index("idx_vecdb_is_default", "is_default"),
        # 同一数据库实例 + 同一维度 不可重复（db_type + connection_string 确定数据库实例）
        Index("uq_vecdb_db_dim", "db_type", "connection_string", "dimension", unique=True),
    )

    def __repr__(self):
        return f"<VectorDBConfig(id={self.id}, type='{self.db_type}', dim={self.dimension})>"


class LLMCacheEntry(Base):
    """
    LLM 处理缓存记录模型

    记录一篇文章的 LLM 处理结果被复用到另一篇文章的记录
    用于统计缓存命中率和审计追踪
    """
    __tablename__ = "llm_cache_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, doc="主键ID")

    source_article_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("articles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="源文章ID（被复用的文章）"
    )

    cached_article_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        doc="缓存文章ID（复用方的文章）"
    )

    similarity_score: Mapped[float] = mapped_column(Float, nullable=False, doc="相似度分数")
    cache_ttl_days: Mapped[int] = mapped_column(Integer, default=1, doc="缓存有效期（天）")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), doc="创建时间")

    __table_args__ = (
        Index("idx_cache_source", "source_article_id"),
        Index("idx_cache_created", "created_at"),
    )

    def __repr__(self):
        return f"<LLMCacheEntry(id={self.id}, src={self.source_article_id}, cached={self.cached_article_id})>"


class ClusterTopic(Base):
    """
    聚类主题模型

    存储每日/每周的主题聚类结果
    """
    __tablename__ = "cluster_topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, doc="主键ID")

    cluster_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, doc="聚类日期")

    keywords: Mapped[str] = mapped_column(Text, nullable=False, doc="关键词")
    article_count: Mapped[int] = mapped_column(Integer, default=1, doc="文章数量")
    avg_score: Mapped[float] = mapped_column(Float, default=0.0, doc="平均评分")
    hotness: Mapped[float] = mapped_column(Float, default=0.0, doc="热度")
    is_emerging: Mapped[bool] = mapped_column(Boolean, default=False, doc="是否新兴主题")

    representative_article_ids: Mapped[Optional[str]] = mapped_column(Text, doc="代表文章ID列表")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), doc="创建时间")

    __table_args__ = (
        Index("idx_cluster_date", "cluster_date"),
        Index("idx_cluster_emerging", "is_emerging"),
    )

    def __repr__(self):
        return f"<ClusterTopic(id={self.id}, kw='{self.keywords[:30]}', count={self.article_count})>"


class ClusterArticle(Base):
    """
    聚类-文章关联表

    多对多关系：一个聚类包含多篇文章
    """
    __tablename__ = "cluster_articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, doc="主键ID")

    cluster_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("cluster_topics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="聚类ID"
    )
    article_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="文章ID"
    )

    __table_args__ = (
        UniqueConstraint("cluster_id", "article_id", name="uq_cluster_article"),
    )

    def __repr__(self):
        return f"<ClusterArticle(cluster_id={self.cluster_id}, article_id={self.article_id})>"


class SystemConfig(Base):
    """
    系统配置模型

    存储用户通过 Web 面板自定义的配置覆盖值。
    采用 Key-Value 稀疏存储：仅存用户修改过的配置，未改过的从 config.py 默认值读取。

    使用方式：
    - ConfigSyncService 启动时从本表加载覆盖值 → setattr 到 settings 对象
    - Web 面板 API 通过 ConfigSyncService 读写本表
    """
    __tablename__ = "system_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, doc="主键ID")

    config_key: Mapped[str] = mapped_column(
        String(80), nullable=False, unique=True, index=True, doc="配置键名（如 push_score_threshold）"
    )
    config_value: Mapped[str] = mapped_column(Text, nullable=False, doc="配置值（JSON 序列化字符串）")
    value_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="str",
        doc="值类型标记：str/int/float/bool，用于反序列化时类型转换"
    )
    category: Mapped[str] = mapped_column(
        String(40), nullable=False, default="general",
        doc="配置分类（score/rss/process/enrich/rsshub/vector/timeout/github/wecom 等）"
    )
    is_encrypted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        doc="是否加密存储（敏感配置如 github_token 为 True）"
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), doc="最后修改时间"
    )

    def __repr__(self):
        return (
            f"<SystemConfig(key='{self.config_key}', "
            f"type='{self.value_type}', "
            f"encrypted={self.is_encrypted})>"
        )
