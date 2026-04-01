# app/services/agentic/tools/__init__.py
from app.services.agentic.tools.basic import get_current_time, save_to_memory, search_memory
from app.services.agentic.tools.news_tools import (
    get_latest_ai_news,
    search_ai_news,
)
from app.services.agentic.tools.github_tools import (
    get_github_trending,
    analyze_github_trend
)

base_tools = [
    get_current_time,
    save_to_memory,
    search_memory
]
ai_news_tools = [
    get_latest_ai_news,
    search_ai_news,
]
github_proj_tools = [
    get_github_trending,
    analyze_github_trend
]


# 所有工具（主 Agent 使用）
all_tools = base_tools + ai_news_tools + github_proj_tools

__all__ = [
    # 工具列表
    "base_tools",
    "ai_news_tools",
    "github_proj_tools",
    "all_tools",
    # 单个工具
    "get_current_time",
    "save_to_memory",
    "search_memory",
    "get_latest_ai_news",
    "search_ai_news",
    "get_github_trending",
    "analyze_github_trend",
]