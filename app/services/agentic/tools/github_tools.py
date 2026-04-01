from langchain.tools import tool
import asyncio

from app.services.fetcher.github_trending import github_fetcher
from typing import Optional, List, Dict
from app.config import get_settings

settings = get_settings()


# ==================== GitHub 工具 ====================

@tool
def get_github_trending(
        language: Optional[str] = None,
        time_range: str = "daily"
) -> str:
    """获取 GitHub 热门项目列表

    当用户询问GitHub热门项目、开源趋势时使用此工具。

    参数：
        language: 编程语言筛选，如 "Python"、"JavaScript"、"Go"，默认为：None
        time_range: 时间范围，可选 "daily"（今日）、"weekly"（本周）、"monthly"（本月），默认为："daily"
    """
    languages = [language] if language else settings.get_github_languages()

    repos = asyncio.run(
        github_fetcher.fetch_multiple_languages(
            limit_per_lang=10,
            time_range=time_range,
            languages=languages
        )
    )

    if not repos:
        lang_filter = f"（{language}）" if language else ""
        return f"暂无{lang_filter}热门项目"

    lang_info = f"（{language}）" if language else ""
    result = f"🔥 获取到 {len(repos)} 个 GitHub 热门{lang_info}项目：\n\n"

    for i, repo in enumerate(repos, 1):
        result += f"{i}. {repo.get('full_name')}\n"
        result += f"   ⭐ {repo.get('stars', 0)} 星 | 💻 {repo.get('language', '未知语言')}\n"
        result += f"   📝 {repo.get('description', '无描述')}\n\n"

    return result


@tool
def analyze_github_trend(
    repos: List[Dict] = None
) -> str:
    """分析 GitHub 热门项目的技术趋势

    当用户想了解技术趋势、流行技术栈时使用此工具。

    参数：
        repos: GitHub项目列表
    """

    if not repos:
        return "暂无数据进行趋势分析"

    # 统计语言分布
    lang_count = {}
    total_stars = 0
    for repo in repos:
        lang = repo.get('language',"未知")
        lang_count[lang] = lang_count.get(lang, 0) + 1
        total_stars += repo.get("stars", 0)

    # 按数量排序
    sorted_langs = sorted(lang_count.items(), key=lambda x: x[1], reverse=True)

    result = f"📊 GitHub 热门项目趋势分析（基于 {len(repos)} 个项目）：\n\n"

    # 语言分布
    result += "🔤 编程语言分布：\n"
    for lang, count in sorted_langs[:5]:
        percentage = (count / len(repos)) * 100
        result += f"   • {lang}: {count} 个项目 ({percentage:.1f}%)\n"

    # 热门项目推荐
    result += "\n🌟 热门项目推荐（按星标数）：\n"
    top_repos = sorted(repos, key=lambda x: x.stars or 0, reverse=True)[:5]
    for i, repo in enumerate(top_repos, 1):
        result += f"   {i}. {repo.get('full_name')} ⭐ {repo.get('stars')}\n"

    # 总体趋势
    avg_stars = total_stars / len(repos) if repos else 0
    result += f"\n📈 总体趋势：\n"
    result += f"   • 平均星标数: {avg_stars:.0f}\n"
    result += f"   • 最热门语言: {sorted_langs[0][0] if sorted_langs else '未知'}\n"

    return result