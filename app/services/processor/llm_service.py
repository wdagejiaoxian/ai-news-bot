# -*- coding: utf-8 -*-
"""
LLM 服务模块

提供统一的LLM调用接口，用于报告内容增强（翻译和优化）
模型选择由 llm_manager 统一管理
"""

import logging
import asyncio
from typing import Dict, Optional

from .llm_manager import llm_manager, LLMMode
from app.config import get_settings

logger = logging.getLogger(__name__)


class LLMService:
    """
    统一LLM服务

    提供各种LLM相关功能的统一入口
    模型可用性由 llm_manager.execute_with_limit() 判断
    """

    async def enhance_report_content(
        self,
        content: str,
        report_type: str = "daily"  # "daily" or "weekly"
    ) -> str:
        """
        使用大模型翻译和优化日报/周报内容

        Args:
            content: 原始报告内容
            report_type: 报告类型 ("daily" 或 "weekly")

        Returns:
            str: 优化后的报告内容
        """
        # 构建提示词
        prompt = f"""
        请对以下{'日报' if report_type == 'daily' else '周报'}内容按要求进行优化：

        ## {'日报' if report_type == 'daily' else '周报'}内容
        {content}

        ## 要求：
        1. 将GitHub热门项目对应的英文描述翻译成中文，保留核心信息（每项不超过50字），语义要保持通畅连贯
        2. 将AI资讯对应的文章摘要进行进一步总结，保留核心信息（每项不超过50字），语义要保持通畅连贯

        ## 输出格式要求：
        1.按原本的结构输出MarkDown文本
        2.不要添加其他任何内容
        """

        # 调用LLM（使用全局管理器限制并发）
        try:
            logger.info('开始调用LLM优化日报/周报内容')
            res = await llm_manager.execute_with_limit(
                self._call_llm,
                prompt=prompt,
                sys_prompt="你是一个专业的翻译和总结专家。"
            )
            if res:
                return res
            else:
                return content

        except Exception as e:
            logger.error(f"翻译git项目描述出错: {e}")
            return content

    async def enhance_article_content(
            self,
            content: str,
    ):
        """对资讯内容进行翻译优化"""
        # 构建提示词
        prompt = f"""请对以下资讯内容按要求进行优化：
## 资讯内容
{content}

## 要求：
1. 将AI资讯对应的英文文章摘要翻译成中文，语义要保持通畅连贯

## 输出格式要求：
1.按原本的结构输出MarkDown文本
2.不要添加其他任何内容
        """
        try:
            logger.info('开始调用LLM翻译资讯摘要内容')
            res = await llm_manager.execute_with_limit(
                self._call_llm,
                prompt=prompt,
                sys_prompt="你是一个专业的翻译助手。"
            )
            if res:
                return res
            else:
                return content

        except Exception as e:
            logger.error(f"翻译资讯摘要出错: {e}")
            return content

    async def _call_llm(
            self,
            prompt,
            sys_prompt = None,
            _selected_model=None,  # 接收传入的模型配置
            _llm_mode=None
    ):
        """调用LLM进行内容增强"""
        # 模型由 llm_manager.execute_with_limit() 保证不为 None
        assert _selected_model is not None, "LLM模型未选中，不应调用此方法"
        api_key = _selected_model.api_key
        api_base = _selected_model.api_base

        import httpx
        settings = get_settings()
        async with httpx.AsyncClient(timeout=settings.batch_llm_timeout) as client:
            http_response = await client.post(
                f"{api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json= {
                    "model": _selected_model.model_name,
                    "messages": [
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                }
            )
        if http_response.status_code == 200:
            logger.info('优化内容完成')
            result = http_response.json()
            return result["choices"][0]["message"]["content"]
        elif http_response.status_code == 429:
            raise Exception("429 Too Many Requests - 触发重试机制")
        else:
            raise Exception(f"API请求失败: {http_response.status_code}")


# 创建全局LLM服务实例
llm_service = LLMService()
