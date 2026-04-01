# -*- coding: utf-8 -*-
"""
配置管理模块
负责加载和管理所有配置项，支持环境变量和 .env 文件
"""

import os

from pathlib import Path
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

# # 项目根目录
# BASE_DIR = Path(__file__).resolve().parent




class Settings(BaseSettings):
    """
    应用配置类
    
    使用 pydantic-settings 自动从环境变量加载配置
    支持 .env 文件配置
    """
    
    # ========== 应用基础配置 ==========
    app_name: str = Field(default="AI News Bot", description="应用名称")
    app_version: str = Field(default="1.0.0", description="应用版本")
    debug: bool = Field(default=False, description="调试模式")
    secret_key: str = Field(default="dev-secret-key", description="密钥")
    
    # ========== 数据库配置 ==========
    database_url: str = Field(
        default="sqlite+aiosqlite:///storage/database.db",
        description="数据库连接URL"
    )
    # llm_memory_url: str = Field(
    #     default="sqlite+aiosqlite:///storage/agent_memory.db",
    #     description="LLM记忆连接URL"
    # )
    # llm_db_path: str = Field(
    #     default=os.path.join(BASE_DIR, "storage", "agent_memory.db"),
    #     description="LLM记忆连接路径"
    # )

    # 报告文件存储路径
    report_storage_path: str = Field(
        default="storage/reports",
        description="报告文件存储路径"
    )

    # ========== LLM配置 ==========
    
    # 本地LLM (摘要) - 如果不配置则使用API方式
    ollama_base_url: Optional[str] = Field(
        default=None,
        description="Ollama API地址，不配置则使用API方式"
    )
    ollama_model: str = Field(
        default="llama3",
        description="用于摘要的本地模型"
    )
    
    # OpenAI API (摘要和评分) - 可分开配置
    openai_api_key: str = Field(default="", description="OpenAI API密钥")
    openai_api_base: str = Field(
        default="https://api.openai.com/v1",
        description="OpenAI API地址，支持OpenAI/Claude/通义等"
    )

    # 硅基流动
    siliconflow_api_key: str = Field(default="", description="硅基流动API密钥")

    siliconflow_api_base: str = Field(
        default="https://api.siliconflow.cn/v1",
        description="硅基流动API地址"
    )
    siliconflow_max_concurrent: int = Field(
        default=1,
        description="硅基流动平台最大并发数"
    )

    # openrouter
    openrouter_api_key: str = Field(default="", description="openrouter平台API密钥")

    openrouter_api_base: str = Field(
        default="https://api.siliconflow.cn/v1",
        description="openrouter平台API地址"
    )
    openrouter_max_concurrent: int = Field(
        default=1,
        description="openrouter平台最大并发数"
    )

    # modelscope
    modelscope_api_key: str = Field(default="", description="modelscope平台API密钥")
    modelscope_api_base: str = Field(
        default="https://api.siliconflow.cn/v1",
        description="modelscope平台API地址"
    )
    modelscope_max_concurrent: int = Field(
        default=1,
        description="modelscope平台最大并发数"
    )

    # 摘要使用的模型 (推荐使用便宜的模型)
    openai_summary_model: str = Field(
        default="gpt-4o-mini",
        description="用于摘要的API模型，推荐gpt-4o-mini或更便宜的"
    )
    
    # 评分使用的模型
    openai_score_model: str = Field(
        default="gpt-4o-mini",
        description="用于评分的API模型"
    )
    
    # ========== GitHub配置 ==========
    github_token: Optional[str] = Field(default=None, description="GitHub API Token")
    
    # ========== 消息推送配置 ==========
    # 企业微信 - 群机器人 (仅推送)
    wecom_webhook_key: str = Field(default="", description="企业微信群机器人Webhook Key")
    
    # 企业微信 - 自建应用 (双向交互)
    wecom_corp_id: str = Field(default="", description="企业ID")
    wecom_agent_id: str = Field(default="", description="自建应用ID")
    wecom_agent_secret: str = Field(default="", description="自建应用密钥")
    wecom_token: str = Field(default="", description="API接收消息Token")
    wecom_aes_key: str = Field(default="", description="API接收消息EncodingAESKey")
    
    # Telegram
    telegram_bot_token: Optional[str] = Field(default=None, description="Telegram Bot Token")
    telegram_chat_id: Optional[str] = Field(default=None, description="Telegram Chat ID")
    
    # ========== 定时任务配置 ==========
    fetch_news_hour: int = Field(default=6, description="新闻采集小时(0-23)")
    fetch_github_hour: int = Field(default=22, description="GitHub采集小时(0-23)")
    daily_report_hour: int = Field(default=23, description="日报推送小时")
    weekly_report_hour: int = Field(default=8, description="周报推送小时")
    weekly_report_day: int = Field(default=0, description="周报推送日期(0=周一)")
    
    # ========== 业务配置 ==========
    push_score_threshold: int = Field(
        default=85,
        description="推送阈值:只有评分>=此值的资讯才会立即推送"
    )

    # 定时任务配置
    cleanup_hour: int = Field(default=3, description="清理低分文章执行小时(0-23)")

    cleanup_days_threshold_min: int = Field(
        default=7,
        description="清理时间阈值，超过此天数并比推送阈值低20分的文章会被清理"
    )

    cleanup_days_threshold_max: int = Field(
        default=30,
        description="清理时间阈值，超过此天数并比推送阈值低10分的文章会被清理"
    )

    
    # 默认RSS源
    default_rss_sources: str = Field(
        default="",
        description="默认RSS源(用|分隔)"
    )
    
    # 默认GitHub语言
    default_github_languages: str = Field(
        default="Python|JavaScript|TypeScript|Go",
        description="默认监控的GitHub语言"
    )
    
    # ========== 模型配置 ==========
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,  # 环境变量不区分大小写
        extra="ignore"  # 忽略额外字段
    )
    
    def get_rss_sources(self) -> List[str]:
        """获取RSS源列表"""
        if not self.default_rss_sources:
            return []
        return [s.strip() for s in self.default_rss_sources.split("|") if s.strip()]
    
    def get_github_languages(self) -> List[str]:
        """获取GitHub语言列表"""
        if not self.default_github_languages:
            return []
        return [s.strip() for s in self.default_github_languages.split("|") if s.strip()]


# 创建全局配置实例
settings = Settings()




def get_settings() -> Settings:
    """获取配置实例"""
    return settings
