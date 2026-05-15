from typing import List, Dict

from langchain.tools import tool
import asyncio

from app.services.processor.deduplicator import deduplicator
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)

settings = get_settings()


# ==================== AI 资讯工具 ====================

@tool
def get_latest_ai_news(
        limit: int = 15,
) -> str:
    """获取最新的 AI 资讯文章

    当用户询问最近的AI新闻、机器学习进展、技术趋势时使用此工具。

    参数：
        limit: 返回文章数量，默认15篇
    """
    logger.info('调用了get_latest_ai_news工具')


    # 从数据库拿数据
    articles = asyncio.run(
        deduplicator.get_recent_articles(
            limit=limit,
            status=["processed","published"]
        )
    )

    if not articles:
        return "暂无最新AI资讯"

    result = f"📰 获取到 {len(articles)} 篇最新AI资讯：\n\n"
    for i, article in enumerate(articles, 1):
        result += f"{i}. {article.title}\n"
        result += f"   📌 来源: {article.source_name}\n"
        result += f"   📝 内容预览: {article.summary}\n"
        result += f"   🔗 [阅读原文]({article.url})\n\n"

    return result


@tool
def search_ai_news(keyword: str, limit: int = 15) -> str:
    """搜索历史 AI 资讯文章

    当用户想查找特定主题的AI文章时使用此工具。

    参数：
        keyword: 搜索关键词
        limit: 返回文章数量，默认15篇
    """
    logger.info('调用了search_ai_news工具')

    articles = asyncio.run(deduplicator.search_articles(keyword, limit=limit))

    if not articles:
        return f"未找到关于'{keyword}'的AI资讯文章"

    result = f"🔍 找到 {len(articles)} 篇关于'{keyword}'的文章：\n\n"
    for i, article in enumerate(articles, 1):
        result += f"{i}. {article.title}\n"
        result += f"   📌 来源: {article.source_name} | ⭐ 评分: {article.score}/100\n"
        result += f"   📝 摘要: {article.summary}\n"
        result += f"   🔗 [阅读原文]({article.url})\n\n"

    return result


@tool
def search_ai_news_semantic(query: str, limit: int = 15) -> str:
    """使用语义搜索查找 AI 资讯文章

    当用户用自然语言描述想找的内容时使用此工具。
    例如："最近关于AI Agent的进展"、"多模态模型的最新突破"。

    参数：
        query: 自然语言查询（可以是句子，不只是关键词）
        limit: 返回文章数量，默认15篇
    """
    logger.info(f'调用了search_ai_news_semantic工具, query={query[:50]}')

    from app.services.vector import vector_service

    results = asyncio.run(
        vector_service.search(query=query, top_k=limit)
    )

    if not results:
        return f"未找到与'{query}'相关的AI资讯文章"

    output = f"🔍 语义搜索：'{query}' 找到 {len(results)} 篇相关文章：\n\n"
    for i, r in enumerate(results, 1):
        output += f"{i}. {r.title}\n"
        output += f"   📌 来源: {r.source_name} | ⭐ 评分: {r.score}/100 | 🎯 相关度: {r.similarity:.0%}\n"
        if r.summary:
            output += f"   📝 {r.summary[:150]}...\n"
        output += f"   🔗 {r.url}\n\n"

    return output


@tool
def get_rag_context(question: str, limit: int = 5) -> str:
    """获取与问题相关的 AI 资讯上下文，用于增强回答质量

    当需要基于最近AI新闻回答用户问题时使用此工具。

    参数：
        question: 用户的问题
        limit: 检索的文章数
    """
    logger.info(f'调用了get_rag_context工具')

    from app.services.vector import vector_service

    contexts = asyncio.run(
        vector_service.retrieve_for_agent(question=question, top_k=limit, score_min=60)
    )

    if not contexts:
        return "暂无相关资讯上下文"

    output = "📚 相关 AI 资讯上下文：\n\n"
    for i, ctx in enumerate(contexts, 1):
        output += f"### {i}. {ctx.title}\n"
        output += f"摘要: {ctx.summary}\n"
        output += f"来源: {ctx.url}\n"
        output += f"相关度: {ctx.similarity:.0%}\n\n"

    return output


# @tool
# def score_ai_article(title: str, summary: str) -> str:
#     """对单篇 AI 文章进行价值评分（0-100分）
#
#     当需要评估单篇文章价值时使用此工具。
#     如果需要对多篇文章批量评分，请使用 batch_score_ai_articles 工具。
#
#     参数：
#         title: 文章标题
#         summary: 文章摘要
#     """
#     logger.info('调用了score_ai_article工具')
#
#     result = asyncio.run(scorer.score_article(title, summary))
#
#     if not result:
#         return "评分失败"
#
#     score = result.get('score', 0)
#     reason = result.get('reason', '无')
#     highlights = result.get('highlights', [])
#
#     return f"📊 文章评分: {score}/10\n💡 评分原因: {reason}\n✨ 亮点: {', '.join(highlights) if highlights else '无'}"
#
#
# @tool
# def batch_score_ai_articles(
#     articles: str,
# ) -> str:
#     """批量对多篇 文章进行价值评分（0-100分）
#
#     当需要对多篇文章进行评分比较或筛选高质量内容时使用此工具。
#     比多次调用 score_ai_article 更高效。
#
#     参数：
#         articles: 包含文章数据的字典数组结构的JSON字符串
#         格式如:
#             [
#                 {"title": "文章1", "summary": "摘要1"},
#                 {"title": "文章2", "summary": "摘要2"}
#             ]
#     返回：
#         按评分降序排列的文章列表，包含评分、原因和亮点
#     """
#     logger.info('调用了batch_score_ai_articles工具')
#
#     if not articles:
#         return "没有需要评分的文章"
#
#     loads_articles = scorer._parse_json_array(articles)
#
#     if not loads_articles:
#         return "传入的JSON数组转换成字典数组失败"
#
#     scores_result = asyncio.run(scorer.batch_score(loads_articles))
#
#     if not scores_result:
#         return "批量评分失败"
#
#     scores_result.sort(key=lambda x: x['score_data']['score'], reverse=True)
#
#     # 格式化输出
#     result = f"📊 批量评分完成，共 {len(scores_result)} 篇文章：\n\n"
#
#     for i, article in enumerate(scores_result, 1):
#         emoji = "🌟" if article['score_data']['score'] >= 85 else "📰"
#         result += f"{emoji} {i}. {article['title']}\n"
#         result += f"   ⭐ 评分: {article['score_data']['score']}/100\n"
#         result += f"   💡 原因: {article['score_data']['reason']}\n"
#         # if article['highlights']:
#         #     result += f"   ✨ 亮点: {', '.join(article['highlights'])}\n"
#         result += "\n"
#
#     # 添加统计信息
#     high_quality = sum(1 for a in scores_result if a['score_data']['score'] >= 85)
#     avg_score = sum(a['score_data']['score'] for a in scores_result) / len(scores_result)
#
#     result += f"📈 统计信息：\n"
#     result += f"   • 高质量文章（≥85分）: {high_quality} 篇\n"
#     result += f"   • 平均评分: {avg_score:.1f}/100\n"
#     result += f"   • 最高评分: {scores_result[0]['score_data']['score']}/100\n"
#
#     return result