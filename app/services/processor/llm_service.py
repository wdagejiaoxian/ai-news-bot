# -*- coding: utf-8 -*-
"""
LLM 服务模块

提供统一的LLM调用接口，用于：
1. 文章摘要生成
2. 内容评分
3. 报告内容增强（翻译和优化）
"""

import logging
import asyncio
from typing import Dict, Optional

from app.config import get_settings
from .llm_manager import llm_manager, LLMMode

logger = logging.getLogger(__name__)


class LLMService:
    """
    统一LLM服务
    
    提供各种LLM相关功能的统一入口
    """
    
    def __init__(self):
        self.settings = get_settings()
        
        # OpenAI API 配置
        self.openai_api_key = self.settings.openai_api_key
        self.openai_api_base = self.settings.openai_api_base
        self.model_name = self.settings.openai_summary_model

        # 判断API是否可用
        self._is_configured = bool(self.openai_api_key)
        
        if self._is_configured:
            logger.info("LLM Service 已配置，使用 OpenAI API")
        else:
            logger.warning("LLM Service 未配置 OpenAI API Key")

    @property
    def is_available(self) -> bool:
        """检查LLM服务是否可用"""
        return self._is_configured

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
        if not self.is_available:
            logger.warning("LLM Service 未配置，跳过内容增强")
            return content
        
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
        if not self.is_available:
            logger.warning("LLM Service 未配置，跳过内容增强")
            return content
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
        # 使用传入的模型配置，如果没有则使用默认值
        api_key = _selected_model.api_key if _selected_model else self.openai_api_key
        api_base = _selected_model.api_base if _selected_model else self.openai_api_base

        format_content = llm_manager.close_think_content(
            selected_model=_selected_model,
            prompt=prompt,
            sys_prompt=sys_prompt
        )

        import httpx
        async def _call_api():
            async with httpx.AsyncClient(timeout=60.0) as client:
                http_response = await client.post(
                    f"{api_base}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=format_content
                )
            return http_response
        response = await _call_api()
        if response.status_code == 200:
            logger.info('优化内容完成')
            result = response.json()
            return result["choices"][0]["message"]["content"]
        elif response.status_code == 429:
            # await asyncio.sleep(5)
            # # 重试一次
            # response = await _call_api()
            # if response.status_code == 200:
            #     logger.info('优化内容完成')
            #     result = response.json()
            #     return result["choices"][0]["message"]["content"]
            # else:
            #     logger.info(f"优化内容失败")
            #     return None
            raise Exception("429 Too Many Requests - 触发重试机制")
        else:
            # logger.info(f"优化内容失败")
            # return None
            raise Exception(f"API请求失败: {response.status_code}")

# 创建全局LLM服务实例
llm_service = LLMService()