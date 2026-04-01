from langchain.tools import tool
from datetime import datetime


# ==================== 基础工具 ====================

@tool
def get_current_time() -> str:
    """获取当前时

    当用户询问当前时间或需要时间戳时使用此工具。
    """
    now = datetime.now()
    return f"当前时间：{now.strftime('%Y年%m月%d日 %H:%M:%S')}"


@tool
def save_to_memory(file_path: str, content: str) -> str:
    """保存信息到长期记忆

    当需要保存用户偏好、重要信息或知识时使用此工具。
    文件路径应以 /memories/ 开头以确保持久化。

    参数：
        file_path: 文件路径，如 /memories/user_preferences.txt
        content: 要保存的内容
    """
    return f"请使用 write_file 工具将内容{content}保存到 {file_path}"


@tool
def search_memory(query: str) -> str:
    """搜索长期记忆中的信息

    当需要查找之前保存的用户偏好、历史交互或知识时使用此工具。

    参数：
        query: 搜索关键词
    """
    return f"请使用 grep 工具在 /memories/ 目录中搜索 '{query}'"