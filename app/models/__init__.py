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
    HACKERNEWS = "hackernews"
    CUSTOM = "custom"


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


# ========== 数据模型 ==========


class Article(Base):
    """
    资讯文章模型
    
    存储从各来源采集的AI资讯文章
    """
    __tablename__ = "articles"
    
    # 主键
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # 唯一标识 (URL哈希)
    url_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    
    # 基本信息
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)  # ArticleSource
    source_name: Mapped[str] = mapped_column(String(100))  # 来源名称如"OpenAI Blog"
    
    # 内容
    summary: Mapped[Optional[str]] = mapped_column(Text)  # LLM生成的摘要
    content: Mapped[Optional[str]] = mapped_column(Text)  # 原始内容(可能截断)
    author: Mapped[Optional[str]] = mapped_column(String(200))
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    # AI处理结果
    tags: Mapped[Optional[str]] = mapped_column(String(500))  # 标签如 "#LLM,#Robotics"
    score: Mapped[Optional[float]] = mapped_column(Float)  # 价值评分 0-10
    keywords: Mapped[Optional[str]] = mapped_column(String(500))  # 关键词
    
    # 状态
    status: Mapped[str] = mapped_column(
        String(20), 
        default=ArticleStatus.PENDING.value,
        index=True
    )
    is_pushed: Mapped[bool] = mapped_column(Boolean, default=False)  # 是否已推送
    pushed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    # 元数据
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(),
        onupdate=func.now()
    )
    
    # 索引
    __table_args__ = (
        Index("idx_article_status_published", "status", "published_at"),
        Index("idx_article_source_status", "source", "status"),
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
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # 唯一标识
    repo_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    
    # 基本信息
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(1000))
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    language: Mapped[Optional[str]] = mapped_column(String(50))
    
    # 统计数据
    stars: Mapped[int] = mapped_column(Integer, default=0)
    forks: Mapped[int] = mapped_column(Integer, default=0)
    stars_today: Mapped[int] = mapped_column(Integer, default=0)  # 今日新增star
    
    # AI处理结果
    summary: Mapped[Optional[str]] = mapped_column(Text)  # 项目简介
    tags: Mapped[Optional[str]] = mapped_column(String(500))  # 标签
    score: Mapped[Optional[float]] = mapped_column(Float)  # 价值评分
    keywords: Mapped[Optional[str]] = mapped_column(String(500))
    
    # 采集信息
    trending_date: Mapped[datetime] = mapped_column(DateTime)  # 采集日期
    trending_range: Mapped[str] = mapped_column(String(20))  # TimeRange
    
    # 状态
    status: Mapped[str] = mapped_column(String(20), default=ArticleStatus.PENDING.value)
    is_pushed: Mapped[bool] = mapped_column(Boolean, default=False)
    pushed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    # 元数据
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(),
        onupdate=func.now()
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
    """
    __tablename__ = "users"
    
    # 主键
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # 用户标识 (Telegram/企业微信用户ID)
    platform: Mapped[str] = mapped_column(String(20), nullable=False)  # wecom/telegram
    platform_id: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # 用户信息
    name: Mapped[Optional[str]] = mapped_column(String(100))
    
    # 订阅设置
    subscribed_topics: Mapped[Optional[str]] = mapped_column(String(500))  # 逗号分隔
    preferred_languages: Mapped[Optional[str]] = mapped_column(String(200))  # GitHub语言
    push_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # 通知时间设置
    daily_report_time: Mapped[Optional[str]] = mapped_column(String(10))  # "08:00"
    weekly_report_time: Mapped[Optional[str]] = mapped_column(String(10))  # "09:00"
    weekly_report_day: Mapped[int] = mapped_column(Integer, default=0)  # 0=周一
    
    # 即时推送阈值 (只推送评分>=此值的内容)
    push_threshold: Mapped[float] = mapped_column(Float, default=8.0)
    
    # 状态
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # 元数据
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    
    __table_args__ = (
        Index("idx_user_platform", "platform", "platform_id", unique=True),
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
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # 源信息
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(50))  # ai/tech/github
    
    # 采集设置
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    fetch_interval: Mapped[int] = mapped_column(Integer, default=60)  # 分钟
    
    # 元数据
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(),
        onupdate=func.now()
    )
    
    # 统计
    last_fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    article_count: Mapped[int] = mapped_column(Integer, default=0)
    
    def __repr__(self):
        return f"<RSSSource(id={self.id}, name='{self.name}', url='{self.url}')>"


class PushLog(Base):
    """
    推送日志模型
    
    记录所有推送历史
    """
    __tablename__ = "push_logs"
    
    # 主键
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # 关联
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    article_id: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("articles.id"),
        nullable=True
    )
    github_repo_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("github_repos.id"),
        nullable=True
    )
    
    # 推送信息
    platform: Mapped[str] = mapped_column(String(20))  # wecom/telegram
    push_type: Mapped[str] = mapped_column(String(20))  # immediate/daily/weekly
    content: Mapped[Text] = mapped_column(Text)
    
    # 状态
    is_success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    
    # 时间
    pushed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<PushLog(id={self.id}, user_id={self.user_id}, type='{self.push_type}')>"
