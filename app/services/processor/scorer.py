# -*- coding: utf-8 -*-
"""
LLM 价值评分模块

使用外部 API (如 OpenAI) 对资讯进行价值评分
只有高评分内容才会触发即时推送

注意：此模块使用付费 API，请配置 API Key
"""

import json
import asyncio
import logging
import re
from typing import Dict, List, Optional

from app.config import get_settings
from .llm_manager import llm_manager, LLMMode

logger = logging.getLogger(__name__)


class Scorer:
    """
    内容价值评分器
    
    使用 OpenAI API 对资讯进行评分
    评分标准:
    - 0-100 分
    - >= 85 分: 高价值，立即推送
    - 60-85 分: 中等价值，加入日报
    - < 60 分: 低价值，忽略
    
    评分维度:
    - 技术创新性
    - 行业影响力
    - 实用性
    - 独特性
    """
    
    # 评分提示词模板
    SCORE_PROMPT_TEMPLATE = """你是一个AI资讯价值评估专家。请对以下资讯进行评分。

=== 评分标准 (0-100分) ===
【90-100分】重大突破：行业里程碑事件、颠覆性技术、影响深远
【80-89分】  重要进展：头部公司动态、重要产品发布、关键技术更新
【70-79分】  值得关注：有意义的技术进展、行业趋势分析
【60-69分】  常规资讯：一般产品更新、普通行业新闻
【40-59分】  价值有限：内容较浅、重复性高、时效性弱
【0-39分】   低价值：营销推广、内容质量差、信息过时

=== 评分维度 ===
1. 技术创新性(25%)：是否有新技术/新方法/新突破，还是常规迭代
2. 商业/战略价值(25%)：投融资、并购、产品发布、市场策略、财报影响
3. 行业影响力 (20%): 对科技生态的波及范围、头部公司参与度、社区讨论度
4. 时效性/稀缺性 (20%): 独家报道、首发优势、紧急安全/政策动态
5. 实用价值(10%)：对开发者/从业者/决策者的参考价值和可操作性

请直接输出JSON格式，不要其他内容:
{{
    "score": 80,
    "reason": "简短的评价原因",
    "highlights": ["亮点1", "亮点2"]
}}

资讯标题: {title}
资讯摘要: {summary}
"""

    # 批量评分提示词
    BATCH_SCORING_PROMPT = """请对以下多条资讯进行批量评分。

=== 评分标准 (0-100分) ===
【90-100分】重大突破：行业里程碑事件、颠覆性技术、影响深远
【80-89分】  重要进展：头部公司动态、重要产品发布、关键技术更新
【70-79分】  值得关注：有意义的技术进展、行业趋势分析
【60-69分】  常规资讯：一般产品更新、普通行业新闻
【40-59分】  价值有限：内容较浅、重复性高、时效性弱
【0-39分】   低价值：营销推广、内容质量差、信息过时

=== 评分维度 ===
1. 技术创新性(25%)：是否有新技术/新方法/新突破，还是常规迭代
2. 商业/战略价值(25%)：投融资、并购、产品发布、市场策略、财报影响
3. 行业影响力 (20%): 对科技生态的波及范围、头部公司参与度、社区讨论度
4. 时效性/稀缺性 (20%): 独家报道、首发优势、紧急安全/政策动态
5. 实用价值(10%)：对开发者/从业者/决策者的参考价值和可操作性

=== 内容类型识别与权重微调 ===
- 硬核技术 (HN/StackOverflow风格): 技术价值权重提升至40%
- 商业科技 (36氪/TechCrunch风格): 商业价值权重提升至40%
- 深度分析 (MIT TR/Wired风格): 影响力与启发性权重提升
- 快讯/短讯: 时效性权重提升，总分上限降低至80分

=== 输出格式 ===
1. 不要使用 markdown 代码块
2. 不要添加任何解释文字
3. 只输出纯 JSON 数组格式
4. 返回的数组中的每一项的index都需要与用户输入的资讯列表的序号相对应
[
    {{"index": 0, "score": 8, "reason": "原因"}},
    {{"index": 1, "score": 6, "reason": "原因"}}
]

=== 资讯列表 ===
{articles}
"""

    def __init__(self):
        self.settings = get_settings()
        self.api_key = self.settings.openai_api_key
        self.api_base = self.settings.openai_api_base
        self.model = self.settings.openai_score_model
        
        # 检查配置
        self._is_configured = bool(self.api_key)
    
    @property
    def is_available(self) -> bool:
        """
        检查评分服务是否可用
        
        Returns:
            bool: 是否配置了 API Key
        """
        return self._is_configured
    
    async def score_article(
        self,
        title: str,
        summary: str,
    ) -> Optional[Dict]:
        """
        对单篇文章进行评分

        Args:
            title: 文章标题
            summary: 文章摘要

        Returns:
            dict or None: 评分结果，包含 score, reason, highlights
        """
        if not self.is_available:
            logger.warning("OpenAI API 未配置，无法评分")
            # return self._default_score("API未配置")
            return None
        if not summary:
            logger.info('评分失败：没有检测到内容')
            return None

        try:
            import httpx

            prompt = self.SCORE_PROMPT_TEMPLATE.format(
                title=title[:200],
                summary=summary[:500],
            )

            result = await llm_manager.execute_with_limit(
                self._call_batch_api,
                llm_mode=LLMMode.THINKING_REQUIRED,
                prompt=prompt,
            )
            return result

            # async def _call_score_api():
            #     async with httpx.AsyncClient(timeout=30.0) as client:
            #         response = await client.post(
            #             f"{self.api_base}/chat/completions",
            #             headers={
            #                 "Authorization": f"Bearer {self.api_key}",
            #                 "Content-Type": "application/json",
            #             },
            #             json={
            #                 "model": self.model,
            #                 "messages": [
            #                     {"role": "system", "content": "你是一个专业的最新资讯价值评估专家。"},
            #                     {"role": "user", "content": prompt}
            #                 ],
            #                 "temperature": 0.3,
            #                 "max_tokens": 2000,
            #             }
            #         )
            #     if response.status_code == 200:
            #         result = response.json()
            #         content = result["choices"][0]["message"]["content"]
            #
            #         # 解析JSON响应
            #         score_data = self._parse_json_response(content)
            #
            #         if score_data:
            #             logger.info(
            #                 f"评分成功: {title[:30]}... -> {score_data.get('score')}分"
            #             )
            #             return score_data
            #         else:
            #             logger.warning(f"评分解析失败: {content[:100]}")
            #             # return self._default_score("解析失败")
            #             return None
            #     else:
            #         logger.error(f"评分请求失败: {response.status_code}")
            #         # return self._default_score(f"API错误: {response.status_code}")
            #         return None
            #
            # result = await llm_manager.execute_with_limit(_call_score_api)
            # return result

        except Exception as e:
            logger.error(f"评分异常: {e}")
            # return self._default_score(f"异常: {str(e)[:20]}")
            return None
    
    async def batch_score(
        self,
        articles: List[Dict]
    ) -> List[Dict] or None:
        """
        批量评分
        
        一次性对多篇文章评分，减少API调用成本
        
        Args:
            articles: 文章列表，每项包含 title, summary, source
        
        Returns:
            List[dict]: 评分结果列表
        """
        if not self.is_available:
            # 返回默认评分
            logger.info('评分失败：API未配置')
            # return [
            #     self._default_score("API未配置") for _ in articles
            # ]
            return None

        if not articles:
            logger.info('评分失败：没有检测到内容')
            return None

        # 构建批量提示词
        articles_text = ""
        for i, article in enumerate(articles):
            articles_text += f"""
{i}.article_id: {article.get('article_id')} 
    标题: {article.get('title', '')[:100]}
    摘要: {article.get('summary', '')[:200]}
    来源: {article.get('source', 'unknown')};
"""
        
        prompt = self.BATCH_SCORING_PROMPT.format(articles=articles_text)
        
        try:

            result = await llm_manager.execute_with_limit(
                self._call_batch_api,
                llm_mode=LLMMode.THINKING_REQUIRED,
                prompt = prompt,
                articles=articles,
            )
            return result


        except Exception as e:
            logger.error(f"批量评分异常: {e}")
            # 失败时返回默认评分


        return None
    async def _call_batch_api(
            self,
            prompt: str,
            articles=None,
            _selected_model=None,  # 接收传入的模型配置
            _llm_mode=None
    ) -> List[Dict] or None:
        """使用传入的模型配置进行批量评分"""
        # 传入的模型配置
        api_key = _selected_model.api_key if _selected_model else self.api_key
        api_base = _selected_model.api_base if _selected_model else self.api_base
        model_name = _selected_model.model_name if _selected_model else self.model



        async def res_success(res):
            result = res.json()
            content = result["choices"][0]["message"]["content"]


            if not articles:
                # 解析JSON响应
                score_data = self._parse_json_response(content)
                logger.info("单篇文章评分成功")
                return score_data

            # 解析JSON数组
            score_data = self._parse_json_array(content)

            if score_data:
                # 将评分结果与文章对应
                for score_item in score_data:
                    idx = score_item.get("index", -1)
                    if 0 <= idx < len(articles):
                        articles[idx]["score_data"] = score_item

                logger.info(f"批量评分成功: {len(articles)} 篇文章")
                return articles
            else:
                logger.warning(f"评分解析失败")
                # return [
                #     {**article, "score_data": self._default_score("评分失败")}
                #     for article in articles
                # ]
                return None
        import httpx
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": "你是一个专业的最新资讯价值评估专家。"},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                }
            )
        if response.status_code == 200:
            return await res_success(response)
        elif response.status_code == 429:
            # await asyncio.sleep(5)
            # # 重试一次
            # response = await _call_api()
            # if response.status_code == 200:
            #     return await res_success(response)
            # else:
            #     logger.error(f"批量评分请求失败: {response.status_code}")
            #     # return [
            #     #     {**article, "score_data": self._default_score("评分失败")}
            #     #     for article in articles
            #     # ]
            #     return None
            raise Exception("429 Too Many Requests - 触发重试机制")
        else:
            # logger.error(f"批量评分请求失败: {response.status_code}")
            # # 失败时返回默认评分
            # # return [
            # #     {**article, "score_data": self._default_score("评分失败")}
            # #     for article in articles
            # # ]
            # return None
            raise Exception(f"批量评分请求失败: {response.status_code}")
        

    
    def _parse_json_response(self, text: str) -> Optional[Dict]:
        """解析JSON响应"""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # 尝试提取 ```json ... ``` 块
        match = re.search(r"```(?:json)?\s*(\{.*?})\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        
        # 尝试提取第一个 { ... } 块
        match = re.search(r"\{.*}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        
        return None
    
    def _parse_json_array(self, text: str) -> List[Dict]:
        """解析JSON数组响应"""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # 尝试提取数组
        match = re.search(r"\[[\s\S]*]", text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        
        return []
    
    # def _default_score(self, reason: str) -> Dict:
    #     """生成默认评分"""
    #     return {
    #         "score": 5.0,
    #         "reason": reason,
    #         "highlights": [],
    #     }
    
    def should_push_immediately(self, score: float, threshold: float = 80.0) -> bool:
        """判断是否应该立即推送"""
        return score >= threshold
    
    async def score_github_repo(
        self,
        full_name: str,
        description: str,
        language: str = None
    ) -> Optional[Dict]:
        """对 GitHub 仓库进行评分"""
        if not self.is_available:
            logger.info('github项目评分失败：API未配置')
            # return self._default_score("API未配置")
            return None

        prompt = f"""评估以下GitHub项目的价值:

项目名: {full_name}
描述: {description}
语言: {language or '未知'}

请评分 (0-10分) 并给出简短理由。
输出JSON格式: {{"score": 8, "reason": "理由"}}
"""
        
        try:
            import httpx
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.api_base}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": "你是GitHub项目评估专家。"},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.3,
                        "max_tokens": 2000,
                    }
                )
            
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                return self._parse_json_response(content)
            
        except Exception as e:
            logger.error(f"GitHub项目评分异常: {e}")
        
        # return self._default_score("评分失败")
        return None

# 创建全局实例
scorer = Scorer()
