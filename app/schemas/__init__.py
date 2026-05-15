# -*- coding: utf-8 -*-
"""
Schema模块
包含所有数据验证模型
"""

from app.api.auth import LoginRequest, RefreshTokenRequest, UserInfoResponse
from app.api.articles import ArticleResponse, ArticleListResponse, ArticleUpdateRequest
from app.api.github import GitHubRepoResponse, GitHubRepoListResponse
from app.api.users import UserResponse, UserListResponse, UserUpdateRequest
from app.api.rss import (
    RSSSourceResponse,
    RSSSourceListResponse,
    RSSSourceCreateRequest,
    RSSSourceUpdateRequest,
)
from app.api.stats import BasicStats, DetailedStats, TrendData
from app.api.scheduler.jobs import JobResponse, JobListResponse, JobTriggerResponse

__all__ = [
    # Auth
    "LoginRequest",
    "RefreshTokenRequest",
    "UserInfoResponse",
    # Articles
    "ArticleResponse",
    "ArticleListResponse",
    "ArticleUpdateRequest",
    # GitHub
    "GitHubRepoResponse",
    "GitHubRepoListResponse",
    # Users
    "UserResponse",
    "UserListResponse",
    "UserUpdateRequest",
    # RSS
    "RSSSourceResponse",
    "RSSSourceListResponse",
    "RSSSourceCreateRequest",
    "RSSSourceUpdateRequest",
    # Stats
    "BasicStats",
    "DetailedStats",
    "TrendData",
    # Scheduler
    "JobResponse",
    "JobListResponse",
    "JobTriggerResponse",
]
