# -*- coding: utf-8 -*-
"""
批量LLM处理模块

专门处理批量文章列表的LLM调用：
- 批量生成摘要+关键词+标签+评分

核心设计：
- 批量调用：每批5篇文章用一次LLM调用
- 批次级并发：信号量控制同时执行的批次数
- 智能降级：批次失败时自动降级到逐篇调用
"""

import asyncio
import json
import logging
import re
from typing import Dict, List, Optional

from .llm_manager import llm_manager, LLMMode
from app.config import get_settings

logger = logging.getLogger(__name__)


class BatchProcessor:
    """
    批量LLM处理器

    使用批量调用 + 批次级并发 + 智能降级策略
    """

    # 列表B模板：摘要+关键词+标签+评分（无摘要的文章）
    BATCH_SKT_TEMPLATE = """请对以下多条资讯进行批量处理：生成摘要、提取关键词、生成标签、进行评分。

=== 任务要求 ===

【摘要】
- 每条资讯生成100-200字的摘要
- 保留核心信息和关键结论
- 使用客观、精炼的语言
- 根据文章类型突出不同重点：
  * 技术突破：突出技术亮点、创新点，性能指标
  * 商业动态：突出交易金额、参与方、战略影响
  * 产品发布：突出功能特性、目标用户、市场定位
  * 深度分析：突出核心观点、数据支撑、趋势判断

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

【评分】
- 请对每条资讯进行价值评分 (0-100分)
- 评分标准：
  * 90-100分：重大突破，行业里程碑事件、颠覆性技术
  * 80-89分：重要进展，头部公司动态、重要产品发布
  * 70-79分：值得关注，有意义的技术进展
  * 60-69分：常规资讯，一般产品更新
  * 40-59分：价值有限，内容较浅
  * 0-39分：低价值，营销推广

=== 输出格式 ===
1. 不要使用 markdown 代码块
2. 不要添加任何解释文字
3. 只输出纯 JSON 数组格式
4. 返回的数组中的每一项的index都需要与用户输入的资讯列表的序号相对应

=== 示例 ===
[
    {{"index": 0, "summary": "摘要内容", "keywords": "关键词 1, 关键词 2, 关键词 3", "tags": "#标签1, #标签2", "score": 85, "reason": "评分原因"}},
    {{"index": 1, "summary": "摘要内容2", "keywords": "关键词 3, 关键词 2, 关键词 5", "tags": "#标签6, #标签1", "score": 72, "reason": "评分原因"}}
]

=== 资讯列表 ===
{articles}
"""

    def __init__(
        self,
        batch_size: int = 5,
        max_batch_concurrent: int = 3,
        max_single_concurrent: int = 5,
    ):
        """
        初始化批量处理器

        :param batch_size: 每批文章数量，默认5
        :param max_batch_concurrent: 批次级最大并发数，默认2
        :param max_single_concurrent: 单篇级最大并发数（用于降级），默认3
        """
        self.batch_size = batch_size
        self.max_batch_concurrent = max_batch_concurrent
        self.max_single_concurrent = max_single_concurrent
        self._batch_semaphore = asyncio.Semaphore(max_batch_concurrent)
        self._single_semaphore = asyncio.Semaphore(max_single_concurrent)

    def split_into_batches(
        self,
        articles: List[Dict],
        batch_size: Optional[int] = None,
    ) -> List[List[Dict]]:
        """
        将文章列表分成多个批次

        :param articles: 文章列表
        :param batch_size: 每批文章数，默认使用self.batch_size
        :return: 批次列表
        """
        size = batch_size or self.batch_size
        return [articles[i:i + size] for i in range(0, len(articles), size)]

    async def process_list_b(
        self,
        articles: List[Dict]
    ) -> List[Dict]:
        """
        处理列表B（无摘要的文章）

        批量调用 + 批次级并发 + 智能降级

        :param articles: 文章列表，每项包含 {"article": Article对象, "title": str, "content": str}
        :return: 处理后的文章列表
        """
        if not articles:
            return []

        # 分批
        batches = self.split_into_batches(articles, self.batch_size)
        logger.info(
            f"开始处理列表B: {len(articles)}篇文章，"
            f"分{len(batches)}批，每批{self.batch_size}篇，"
            f"批次并发数={self.max_batch_concurrent}"
        )

        async def process_batch(batch: List[Dict]) -> List[Dict]:
            """处理一个批次"""
            async with self._batch_semaphore:
                try:
                    # 构建批量提示词
                    articles_text = self._build_batch_skt_text(batch)
                    prompt = self.BATCH_SKT_TEMPLATE.format(articles=articles_text)

                    # 调用批量LLM
                    result = await llm_manager.execute_with_limit(
                        self._batch_call_skt,
                        llm_mode=LLMMode.THINKING_REQUIRED,
                        prompt=prompt,
                        batch=batch,
                    )

                    if result:
                        logger.info(f"批次处理成功: {len(batch)}篇")
                        return result
                    else:
                        # 降级：逐篇调用
                        logger.warning(f"批次处理返回空，降级到逐篇调用")
                        return await self._retry_batch_singly(batch, self._process_single_skt)

                except Exception as e:
                    logger.error(f"批次处理异常: {e}，降级到逐篇调用")
                    return await self._retry_batch_singly(batch, self._process_single_skt)

        # 并发执行所有批次
        tasks = [process_batch(b) for b in batches]
        batch_results: list = await asyncio.gather(*tasks, return_exceptions=True)

        # 收集结果
        processed = []
        for result in batch_results:
            if isinstance(result, Exception):
                logger.error(f"批次异常: {result}")
                continue
            processed.extend(result)

        logger.info(f"列表B处理完成: 成功{len(processed)}/{len(articles)}篇")
        return processed

    def _build_batch_skt_text(self, batch: List[Dict]) -> str:
        """
        构建列表B的批量提示词文本（无摘要）

        :param batch: 批次文章列表
        """
        articles_text = ""
        for i, item in enumerate(batch):
            title = item.get("title", "")[:100] or ""
            content = item.get("content", "")[:500] or ""
            articles_text += f"""
{i}.文章标题: {title}
   文章内容: {content}
"""
        return articles_text

    async def _batch_call_skt(
        self,
        prompt: str,
        batch: List[Dict],
        _selected_model=None,
        _llm_mode=None,
    ) -> List[Dict]:
        """
        批量调用LLM生成摘要+关键词+标签+评分

        :param prompt: 提示词
        :param batch: 文章批次
        :param _selected_model: 传入的模型配置
        :param _llm_mode:
        :return: 处理后的批次
        """
        import httpx
        settings = get_settings()

        # 模型由 llm_manager.execute_with_limit() 保证不为 None
        assert _selected_model is not None, "LLM模型未选中，不应调用此方法"
        api_key = _selected_model.api_key
        api_base = _selected_model.api_base
        model_name = _selected_model.model_name

        sys_prompt = "你是一个专业的AI资讯处理助手，擅长生成摘要、提取关键词、生成标签和评分。"

        async with httpx.AsyncClient(timeout=settings.batch_llm_timeout) as client:
            response = await client.post(
                f"{api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                }
            )

        if response.status_code == 200:
            return self._parse_batch_skt_response(response, batch)
        elif response.status_code == 429:
            raise Exception("429 Too Many Requests - 触发重试机制")
        else:
            raise Exception(f"API请求失败: {response.status_code}")

    def _parse_batch_skt_response(
        self,
        response,
        batch: List[Dict],
    ) -> List[Dict]:
        """
        解析批量LLM响应（摘要+关键词+标签+评分）

        :param response: LLM响应对象
        :param batch: 文章批次
        :return: 更新后的批次
        """
        result = response.json()
        content = result["choices"][0]["message"]["content"]

        parsed = self._parse_json_array(content)
        if not parsed:
            logger.warning("批量SKT响应解析失败")
            return batch

        # 将解析结果与文章对应
        for item in parsed:
            idx = item.get("index", -1)
            if 0 <= idx < len(batch):
                article = batch[idx].get("article")
                if article:
                    article.summary = self._clean_summary(item.get("summary", ""))
                    article.keywords = item.get("keywords", "")
                    article.tags = self._parse_tags(item.get("tags", ""))
                    article.score = item.get("score", 0)
                    article.score_reason = item.get("reason", "")

        return batch

    async def _retry_batch_singly(
        self,
        batch: List[Dict],
        process_func,
    ) -> List[Dict]:
        """
        批次失败后，逐篇重试

        :param batch: 文章批次
        :param process_func: 单篇处理函数
        :return: 处理后的批次
        """
        logger.info(f"开始逐篇重试批次: {len(batch)}篇")

        async def process_one(article_dict: Dict) -> Dict:
            async with self._single_semaphore:
                try:
                    return await process_func(article_dict)
                except Exception as e:
                    logger.error(f"单篇重试失败: {article_dict.get('title', 'unknown')[:30]}... 错误: {e}")
                    return article_dict

        tasks = [process_one(a) for a in batch]
        results: list = await asyncio.gather(*tasks, return_exceptions=True)

        return [r for r in results if not isinstance(r, Exception)]

    async def _process_single_skt(self, article_dict: Dict) -> Dict:
        """单篇SKT处理（用于降级）"""
        prompt = self._build_single_skt_prompt(article_dict)

        result = await llm_manager.execute_with_limit(
            self._call_single_skt,
            llm_mode=LLMMode.THINKING_REQUIRED,
            prompt=prompt,
            article_dict=article_dict,
        )
        return result if result else article_dict

    def _build_single_skt_prompt(self, article_dict: Dict) -> str:
        """构建单篇SKT提示词"""
        title = article_dict.get("title", "")[:100]
        content = article_dict.get("content", "")[:2000]

        return f"""请对以下资讯进行处理：生成摘要、提取关键词、生成标签、进行评分。

文章标题: {title}
文章内容:
{content}

=== 任务要求 ===
【摘要】100-200字，保留核心信息
【关键词】3-8个，使用英文逗号分隔
【标签】2-5个，使用 # 开头
【评分】0-100分

请直接输出JSON格式，不要其他内容:
{{"summary": "摘要内容...", "keywords": "关键词1, 关键词2, 关键词3", "tags": "#标签1, #标签2", "score": 85, "reason": "评分原因"}}
"""

    async def _call_single_skt(
        self,
        prompt: str,
        article_dict: Dict,
        _selected_model=None,
        _llm_mode=None,
    ) -> Dict:
        """单篇调用LLM生成摘要+关键词+标签+评分"""
        import httpx
        settings = get_settings()

        # 模型由 llm_manager.execute_with_limit() 保证不为 None
        assert _selected_model is not None, "LLM模型未选中，不应调用此方法"
        api_key = _selected_model.api_key
        api_base = _selected_model.api_base
        model_name = _selected_model.model_name

        sys_prompt = "你是一个专业的AI资讯处理助手，擅长生成摘要、提取关键词、生成标签和评分。"

        async with httpx.AsyncClient(timeout=settings.batch_llm_timeout) as client:
            response = await client.post(
                f"{api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                }
            )

        if response.status_code == 200:
            return self._parse_single_skt_response(response, article_dict)
        elif response.status_code == 429:
            raise Exception("429 Too Many Requests - 触发重试机制")
        else:
            raise Exception(f"API请求失败: {response.status_code}")

    def _parse_single_skt_response(self, response, article_dict: Dict) -> Dict:
        """解析单篇SKT响应"""
        result = response.json()
        content = result["choices"][0]["message"]["content"]

        parsed = self._parse_json_object(content)
        if parsed:
            article = article_dict.get("article")
            if article:
                article.summary = self._clean_summary(parsed.get("summary", ""))
                article.keywords = parsed.get("keywords", "")
                article.tags = self._parse_tags(parsed.get("tags", ""))
                article.score = parsed.get("score", 0)
                article.score_reason = parsed.get("reason", "")

        return article_dict

    def _parse_json_object(self, text: str) -> Dict:
        """解析JSON对象响应"""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 尝试提取 ```json ... ``` 块
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
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

        return {}

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

    def _clean_summary(self, text: str) -> str:
        """清理摘要"""
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r"^摘要[:：]\s*", "", text)
        # 限制长度
        if len(text) > 200:
            sentences = text.split("。")
            result = ""
            for s in sentences:
                if len(result) + len(s) + 1 <= 200:
                    result += s + "。"
                else:
                    break
            text = result or text[:200]
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


# 创建全局实例
# batch_size=5: 每批5篇文章
# max_batch_concurrent=2: 最多2个批次并发执行
batch_processor = BatchProcessor(
    batch_size=5,
    max_batch_concurrent=2,
    max_single_concurrent=3,
)
