# -*- coding: utf-8 -*-
"""
LLM 摘要生成模块

支持两种方式：
1. 本地 Ollama 模型 (免费，需额外部署)
2. OpenAI API (付费，使用配置中的API Key)

优先使用本地Ollama，如果未配置则使用API
"""

import logging
import asyncio
import re
import json
from typing import Dict, Optional, List

from app.config import get_settings
from .llm_manager import llm_manager, LLMMode

logger = logging.getLogger(__name__)


class Summarizer:
    """
    文章摘要生成器
    
    支持:
    - 本地 Ollama 模型 (优先)
    - OpenAI API (备选)
    
    当未配置 Ollama 时，自动使用 API 方式
    """
    
    # 摘要提示词模板
    SUMMARY_PROMPT_TEMPLATE = """你是一个专业的AI资讯摘要助手。请阅读以下文章内容，
生成一个简洁、准确的摘要。

要求:
1. 摘要长度控制在 100-200 字
2. 保留核心信息和关键结论
3. 使用客观、精炼的语言
4. 如果是技术文章，突出技术亮点和创新点

文章标题: {title}

文章内容:
{content}

请直接输出摘要，不需要其他内容:"""

    # 关键词提取提示词
    KEYWORDS_PROMPT_TEMPLATE = """从以下文章标题和摘要中提取关键词。

要求:
1. 提取 3-8 个关键词或短语
2. 使用英文逗号分隔
3. 优先选择技术术语和领域关键词
4. 格式: 关键词1, 关键词2, 关键词3

标题: {title}
摘要: {summary}

请直接输出关键词，不需要其他内容:"""

    # 标签生成提示词
    TAGS_PROMPT_TEMPLATE = """根据以下文章内容，生成合适的标签。

要求:
1. 生成 2-5 个标签
2. 使用 # 开头
3. 标签应该反映文章的主题领域
4. 可用的标签: #AI, #LLM, #GPT, #Robotics, #MachineLearning, 
   #OpenAI, #Google, #Microsoft, #Startup, #Research, #Tech

标题: {title}
内容: {content}

请直接输出标签，不需要其他内容:"""

    # 关键词和标签生成提示词
    TAGS_KEYWORDS_PROMPT_TEMPLATE = """请对以下多条资讯进行批量提取关键词、生成标签。
=== 任务要求 ===
【关键词】
- 每条资讯提取 3-8 个关键词或短语
- 使用英文逗号分隔
- 优先选择：
  * 技术术语（模型架构、算法、编程语言）
  * 公司/机构名称
  * 产品/项目名称
  * 领域关键词（如：生成式AI、云计算、半导体）
  * 商业术语（如：IPO、并购、融资轮次）

【标签】
- 每条资讯生成 2-5 个标签
- 使用 # 开头
- 标签体系（可多选）：
  * 领域: #AI, #云计算, #半导体, #生物科技, #新能源, #区块链, #网络安全, #消费电子, #企业服务, #金融科技
  * 技术: #LLM, #AIGC, #大模型, #自动驾驶, #机器人, #5G, #物联网, #边缘计算, #量子计算
  * 主题: #融资, #产品发布, #技术突破, #行业分析, #政策解读, #人物动态, #并购, #开源
  * 影响层级：#行业里程碑, #值得关注, #常规资讯

=== 输出格式 ===
1. 不要使用 markdown 代码块
2. 不要添加任何解释文字
3. 只输出纯 JSON 数组格式
4. 返回的数组中的每一项的index都需要与用户输入的资讯列表的序号相对应

=== 示例 ===
[
    {{"index": 0, "keywords": "关键词 1, 关键词 2, 关键词 3", "tags": "#标签1, #标签2"}},
    {{"index": 1, "keywords": "关键词 3, 关键词 2, 关键词 5", "tags": "#标签6, #标签1"}}
]

=== 资讯列表 ===
{articles}
"""

    # 综合提示词模板
    COMBINED_PROMPT_TEMPLATE = """请阅读以下文章内容，完成三个任务：生成摘要、提取关键词、生成标签。
文章标题: {title}
文章内容: {content}

=== 任务要求 ===

【摘要】
- 长度控制在 100-200 字
- 保留核心信息和关键结论
- 使用客观、精炼的语言
- 根据文章类型突出不同重点：
  * 技术突破：突出技术亮点、创新点、性能指标
  * 商业动态：突出交易金额、参与方、战略影响
  * 产品发布：突出功能特性、目标用户、市场定位
  * 深度分析：突出核心观点、数据支撑、趋势判断
  * 政策/安全：突出影响范围、合规要求、行业反应

【关键词】
- 提取 3-8 个关键词或短语
- 使用英文逗号分隔
- 优先选择：
  * 技术术语（模型架构、算法、编程语言）
  * 公司/机构名称
  * 产品/项目名称
  * 领域关键词（如：生成式AI、云计算、半导体）
  * 商业术语（如：IPO、并购、融资轮次）

【标签】
- 生成 2-5 个标签
- 使用 # 开头
- 标签体系（可多选）：
  * 领域: #AI, #云计算, #半导体, #生物科技, #新能源, #区块链, #网络安全, #消费电子, #企业服务, #金融科技
  * 技术: #LLM, #AIGC, #大模型, #自动驾驶, #机器人, #5G, #物联网, #边缘计算, #量子计算
  * 主题: #融资, #产品发布, #技术突破, #行业分析, #政策解读, #人物动态, #并购, #开源
  * 影响层级：#行业里程碑, #值得关注, #常规资讯

=== 输出格式 ===
1. 不要使用 markdown 代码块（不要用 ```json）
2. 不要添加任何解释文字
3. 只输出纯 JSON 字符串

=== 示例 ===
{{
    "summary": "摘要内容",
    "keywords": "关键词 1, 关键词 2, 关键词 3",
    "tags": "#标签1, #标签2"
}}
    """

    def __init__(self):
        self.settings = get_settings()
        
        # Ollama 配置
        self.ollama_url = self.settings.ollama_base_url
        self.ollama_model = self.settings.ollama_model
        
        # OpenAI API 配置
        self.openai_api_key = self.settings.openai_api_key
        self.openai_api_base = self.settings.openai_api_base
        self.openai_summary_model = self.settings.openai_summary_model
        
        # 判断使用哪种方式
        self._use_ollama = False
        self._use_api = False
        
        self._check_available()
    
    def _check_available(self):
        """检查可用的模型方式"""
        # 优先检查 Ollama
        if self.ollama_url:
            if self._check_ollama():
                self._use_ollama = True
                logger.info("使用本地 Ollama 进行摘要")
                return
        
        # 其次检查 OpenAI API
        if self.openai_api_key:
            self._use_api = True
            logger.info("使用 OpenAI API 进行摘要")
            return
        
        # 都没有配置
        logger.warning("未配置 Ollama 和 OpenAI API，无法生成摘要")
    
    @property
    def is_available(self) -> bool:
        """检查是否可用"""
        return self._use_ollama or self._use_api
    
    def _check_ollama(self) -> bool:
        """检查 Ollama 服务"""
        if not self.ollama_url:
            return False
            
        import httpx
        
        try:
            response = httpx.get(
                f"{self.ollama_url}/api/tags",
                timeout=5.0
            )
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m.get("name", "").split(":")[0] for m in models]
                
                if self.ollama_model.split(":")[0] in model_names:
                    return True
            return False
        except Exception as e:
            logger.debug(f"Ollama 检查失败: {e}")
            return False
    
    async def summarize(
        self,
        title: str,
        content: str,
        max_length: int = 200
    ) -> dict[str, str] | None:
        """生成文章摘要、关键词、标签"""
        if not self.is_available:
            logger.warning("无可用的摘要和关键词标签服务")
            return None
        
        # 截断内容
        content = content[:3000]
        
        if self._use_ollama:
            return await self._summarize_with_ollama(title, content, max_length)
        elif self._use_api:
            return await self._summarize_with_api(title, content, max_length)
        
        return None
    
    async def _summarize_with_ollama(
        self,
        title: str,
        content: str,
        max_length: int
    ) -> dict[str, str] | None:
        """使用 Ollama 生成摘要、关键词、标签"""
        import httpx
        
        try:
            prompt = self.COMBINED_PROMPT_TEMPLATE.format(
                title=title[:200],
                content=content
            )
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.ollama_model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.3,
                            "num_predict": 300,
                        }
                    },
                    timeout=60.0
                )
            
            if response.status_code == 200:
                return await self.res_success(response,max_length)
                # result = response.json()
                # summary = result.get("response", "").strip()
                # return self._clean_summary(summary, max_length)
            
            return None
        except Exception as e:
            logger.error(f"Ollama 摘要失败: {e}")
            return None
    
    async def _summarize_with_api(
        self,
        title: str,
        content: str,
        max_length: int
    ) -> dict[str, str] | None:
        """使用 OpenAI API 生成摘要、关键词、标签"""

        
        try:
            prompt = self.COMBINED_PROMPT_TEMPLATE.format(
                title=title[:200],
                content=content
            )
            result = await llm_manager.execute_with_limit(
                self._call_llm_api,
                prompt=prompt,
                max_length = max_length
            )
            return result

        except Exception as e:
            logger.error(f"API 摘要失败: {e}")
            return None

    async def batch_extract_tags_keywords(
            self,
            batch: list[dict[str, str]],
    ) -> List[Dict] or None:
        """生成关键词、标签"""
        if not self.is_available:
            logger.warning("无可用的摘要和关键词标签服务")
            return None

        if self._use_ollama:
            return await self._extract_kt_with_ollama(batch)
        elif self._use_api:
            return await self._extract_kt_with_api(batch)

        return None

    async def _extract_kt_with_ollama(
            self,
            batch: list[dict[str, str]],
    ) -> List[Dict] or None:
        """使用 Ollama 生成关键词、标签"""
        import httpx

        try:
            # 构建批量提示词
            articles_text = ""
            for i, article in enumerate(batch):
                articles_text += f"""
            {i}.文章标题: {article.get('title', '')[:100]}
                文章内容: {article.get('content', '')[:200]}\n
            """

            prompt = self.TAGS_KEYWORDS_PROMPT_TEMPLATE.format(articles=articles_text)

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.ollama_model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.3,
                            "num_predict": 300,
                        }
                    },
                    timeout=60.0
                )

            if response.status_code == 200:
                return await self.batch_res_success(response, batch)
                # result = response.json()
                # summary = result.get("response", "").strip()
                # return self._clean_summary(summary, max_length)

            return None
        except Exception as e:
            logger.error(f"Ollama 摘要失败: {e}")
            return None

    async def _extract_kt_with_api(
            self,
            batch: list[dict[str, str]],
    ) -> List[Dict] or None:
        """使用 OpenAI API 生成摘要、关键词、标签"""

        try:
            # 构建批量提示词
            articles_text = ""
            for i, article in enumerate(batch):
                articles_text += f"""
                        {i}.文章标题: {article.get('title', '')[:100]}
                            文章内容: {article.get('content', '')[:200]}\n
                        """

            prompt = self.TAGS_KEYWORDS_PROMPT_TEMPLATE.format(articles=articles_text)

            result = await llm_manager.execute_with_limit(
                self._call_llm_api,
                prompt=prompt,
                batch = batch,
                sys_prompt = "你是一个专业的文章关键词提取和标签生成专家",
                many = True
            )
            return result

        except Exception as e:
            logger.error(f"API 摘要失败: {e}")
            return None

    async def res_success(self,res, max_length):
        """
        调用模型提取摘要、关键词、标签成功后数据的处理
        :param res: 模型返回的结果对象
        :param max_length: 摘要的最长长度
        :return: 一个处理好且包含摘要、关键词、标签的字典
        """

        result = res.json()
        result_obj = json.loads(result["choices"][0]["message"]["content"].strip())
        summary = self._clean_summary(result_obj.get('summary'), max_length)
        keywords = self._clean_keywords(result_obj.get('keywords'))
        tags = self._parse_tags(result_obj.get('tags'))
        return {
            "summary": summary,
            "keywords": keywords,
            "tags": tags
        }

    async def batch_res_success(self,res,batch):
        result = res.json()
        content = result["choices"][0]["message"]["content"]

        # 解析JSON数组
        tags_keywords_res = self._parse_json_array(content)

        if tags_keywords_res:
            # 将评分结果与文章对应
            for item in tags_keywords_res:
                idx = item.get("index", -1)
                if 0 <= idx < len(batch):
                    batch[idx]["article"].keywords = item.get("keywords", "")
                    batch[idx]["article"].tags = item.get("tags", "")

            logger.info(f"批量提取关键词、标签成功: {len(batch)} 篇文章")
            return batch
        else:
            logger.warning(f"批量提取关键词、标签失败")
            # return [
            #     {**article, "score_data": self._default_score("评分失败")}
            #     for article in articles
            # ]
            return None
            
    async def _call_llm_api(
            self,
            prompt,
            max_length = 200,
            batch=None,
            sys_prompt = "你是一个专业的AI资讯处理助手。",
            many = False,
            _selected_model=None,  # 接收传入的模型配置
            _llm_mode=None
    ):
        """
        调用模型并判断返回结果是否成功
        :param prompt: 提示词
        :param max_length: 返回的摘要最大长度
        :param batch: 批数量
        :param sys_prompt: 系统提示词
        :param many: 是否批量处理
        :param _selected_model: 传入的模型配置
        :param _llm_mode:
        :return: 响应成功的数据或者None
        """
        if batch is None:
            batch = []

        # 使用传入的模型配置，如果没有则使用默认值
        api_key = _selected_model.api_key if _selected_model else self.openai_api_key
        api_base = _selected_model.api_base if _selected_model else self.openai_api_base

        format_content = llm_manager.close_think_content(
            selected_model=_selected_model,
            prompt=prompt,
            sys_prompt=sys_prompt,
        )

        import httpx
        # async def _call_api():
        #     async with httpx.AsyncClient(timeout=60.0) as client:
        #         http_response = await client.post(
        #             f"{api_base}/chat/completions",
        #             headers={
        #                 "Authorization": f"Bearer {api_key}",
        #                 "Content-Type": "application/json",
        #             },
        #             json={
        #                 "model": model_name,
        #                 "messages": [
        #                     {"role": "system", "content": sys_prompt},
        #                     {"role": "user", "content": prompt}
        #                 ],
        #                 "temperature": 0.3,
        #                 "max_tokens": 400,
        #                 # "thinking": {
        #                 #     "type": "disabled"
        #                 # }
        #                 "enable_thinking": False
        #             }
        #         )
        #     return http_response

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=format_content
            )

        if response.status_code == 200:
            if many:
                return await self.batch_res_success(response, batch)
            return await self.res_success(response, max_length)
        elif response.status_code == 429:
            # await asyncio.sleep(5)
            # # 重试一次
            # response = await _call_api()
            # if response.status_code == 200:
            #     if many:
            #         return await self.batch_res_success(response, batch)
            #     return await self.res_success(response, max_length)
            raise Exception("429 Too Many Requests - 触发重试机制")
        else:
            raise Exception(f"API请求失败: {response.status_code}")
        # return None


    
    # async def extract_keywords(self, title: str, summary: str) -> Optional[str]:
    #     """提取关键词"""
    #     if not self.is_available:
    #         return None
    #
    #     if self._use_ollama:
    #         return await self._extract_keywords_ollama(title, summary)
    #     elif self._use_api:
    #         return await self._extract_keywords_api(title, summary)
    #
    #     return None
    #
    # async def _extract_keywords_ollama(self, title: str, summary: str) -> Optional[str]:
    #     """使用 Ollama 提取关键词"""
    #     import httpx
    #
    #     try:
    #         prompt = self.KEYWORDS_PROMPT_TEMPLATE.format(
    #             title=title[:200],
    #             summary=summary[:500]
    #         )
    #
    #         async with httpx.AsyncClient() as client:
    #             response = await client.post(
    #                 f"{self.ollama_url}/api/generate",
    #                 json={
    #                     "model": self.ollama_model,
    #                     "prompt": prompt,
    #                     "stream": False,
    #                     "options": {"temperature": 0.3, "num_predict": 100}
    #                 },
    #                 timeout=30.0
    #             )
    #
    #         if response.status_code == 200:
    #             keywords = response.json().get("response", "").strip()
    #             return self._clean_keywords(keywords)
    #
    #         return None
    #     except Exception:
    #         return None
    
    # async def _extract_keywords_api(self, title: str, summary: str) -> Optional[str]:
    #     """使用 API 提取关键词"""
    #     import httpx
    #
    #     try:
    #         prompt = self.KEYWORDS_PROMPT_TEMPLATE.format(
    #             title=title[:200],
    #             summary=summary[:500]
    #         )
    #
    #         async with httpx.AsyncClient(timeout=30.0) as client:
    #             response = await client.post(
    #                 f"{self.openai_api_base}/chat/completions",
    #                 headers={
    #                     "Authorization": f"Bearer {self.openai_api_key}",
    #                     "Content-Type": "application/json",
    #                 },
    #                 json={
    #                     "model": self.openai_summary_model,
    #                     "messages": [
    #                         {"role": "system", "content": "你是一个关键词提取助手。"},
    #                         {"role": "user", "content": prompt}
    #                     ],
    #                     "temperature": 0.3,
    #                     "max_tokens": 2000,
    #                 }
    #             )
    #
    #         if response.status_code == 200:
    #             keywords = response.json()["choices"][0]["message"]["content"].strip()
    #             return self._clean_keywords(keywords)
    #         elif response.status_code == 429:
    #             await asyncio.sleep(5)
    #
    #         return None
    #     except Exception:
    #         return None
    #
    # async def generate_tags(self, title: str, content: str) -> Optional[str]:
    #     """生成标签"""
    #     if not self.is_available:
    #         return None
    #
    #     content = content[:1000]
    #
    #     if self._use_ollama:
    #         return await self._generate_tags_ollama(title, content)
    #     elif self._use_api:
    #         return await self._generate_tags_api(title, content)
    #
    #     return None
    
    # async def _generate_tags_ollama(self, title: str, content: str) -> Optional[str]:
    #     """使用 Ollama 生成标签"""
    #     import httpx
    #
    #     try:
    #         prompt = self.TAGS_PROMPT_TEMPLATE.format(
    #             title=title[:200],
    #             content=content
    #         )
    #
    #         async with httpx.AsyncClient() as client:
    #             response = await client.post(
    #                 f"{self.ollama_url}/api/generate",
    #                 json={
    #                     "model": self.ollama_model,
    #                     "prompt": prompt,
    #                     "stream": False,
    #                     "options": {"temperature": 0.3, "num_predict": 100}
    #                 },
    #                 timeout=30.0
    #             )
    #
    #         if response.status_code == 200:
    #             tags = response.json().get("response", "").strip()
    #             return self._parse_tags(tags)
    #
    #         return None
    #     except Exception:
    #         return None
    
    # async def _generate_tags_api(self, title: str, content: str) -> Optional[str]:
    #     """使用 API 生成标签"""
    #     import httpx
    #
    #     try:
    #         prompt = self.TAGS_PROMPT_TEMPLATE.format(
    #             title=title[:200],
    #             content=content
    #         )
    #
    #         async with httpx.AsyncClient(timeout=30.0) as client:
    #             response = await client.post(
    #                 f"{self.openai_api_base}/chat/completions",
    #                 headers={
    #                     "Authorization": f"Bearer {self.openai_api_key}",
    #                     "Content-Type": "application/json",
    #                 },
    #                 json={
    #                     "model": self.openai_summary_model,
    #                     "messages": [
    #                         {"role": "system", "content": "你是一个标签生成助手。"},
    #                         {"role": "user", "content": prompt}
    #                     ],
    #                     "temperature": 0.3,
    #                     "max_tokens": 2000,
    #                 }
    #             )
    #
    #         if response.status_code == 200:
    #             tags = response.json()["choices"][0]["message"]["content"].strip()
    #             return self._parse_tags(tags)
    #         elif response.status_code == 429:
    #             await asyncio.sleep(5)
    #         return None
    #     except Exception:
    #         return None

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

    def _clean_summary(self, text: str, max_length: int) -> str:
        """清理摘要"""
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r"^摘要[:：]\s*", "", text)
        
        if len(text) > max_length:
            sentences = text.split("。")
            result = ""
            for s in sentences:
                if len(result) + len(s) + 1 <= max_length:
                    result += s + "。"
                else:
                    break
            text = result or text[:max_length]
        
        return text
    
    def _clean_keywords(self, text: str) -> str:
        """清理关键词"""
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r"^关键词[:：]\s*", "", text)
        text = text.strip(" ,。、")
        return text
    
    def _parse_tags(self, text: str) -> str:
        """解析标签"""
        tags = re.findall(r"#\w+", text)
        if tags:
            return ",".join(tags)
        
        text = text.strip()
        text = re.sub(r"[\n\r]+", ",", text)
        text = re.sub(r"\s+", "", text)
        text = text.strip(",")

        if text:
            parts = text.split(",")
            return ",".join(f"#{p}" for p in parts)
        return text
    
    async def process_article(
        self,
        title: str,
        content: str
    ) -> Dict[str, str]:
        """处理文章，生成摘要、关键词和标签"""
        result = {
            "summary": None,
            "keywords": None,
            "tags": None,
        }
        res = await self.summarize(title, content)

        if not res:
            return result

        result["summary"] = res.get('summary')

        # keywords = await self.extract_keywords(title, summary)
        result["keywords"] = res.get('keywords')

        # tags = await self.generate_tags(title, content[:1000])
        result["tags"] = res.get('tags')

        return result


# 创建全局实例
summarizer = Summarizer()
