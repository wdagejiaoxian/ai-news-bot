"""
工具缓存中间件 - 完整版

使用LangChain的wrap_tool_call实现工具拦截和缓存
"""

import json
import logging
from typing import Any, Callable
from langchain.agents.middleware import wrap_tool_call, AgentMiddleware

logger = logging.getLogger(__name__)


class ToolCacheMiddleware:
    """工具缓存中间件类"""

    def __init__(
            self,
            cache_store,
            ttl_seconds: int = 600,
    ):
        """
        初始化中间件

        Args:
            cache_store: 缓存存储对象（支持get/set/delete方法）
            ttl_seconds: 缓存过期时间
        """
        self.cache_store = cache_store
        self.ttl = ttl_seconds
        self._tool_results = {}  # 内存缓存备份

    def _get_from_cache(
            self,
            tool_name: str,
            **kwargs
    ) -> Any:
        """从缓存获取结果"""
        try:
            # 只使用内存缓存，避免 SqliteStore 事务问题
            mem_key = self._make_key(tool_name, **kwargs)

            if mem_key in self._tool_results:
                logger.info(f'[中间件缓存] 命中: {tool_name}')
                cached = self._tool_results[mem_key]
                # 如果缓存的是字符串，直接返回
                # 如果是 ToolMessage，需要重新构造
                if isinstance(cached, dict) and cached.get('type') == 'toolmessage':
                    from langchain.messages import ToolMessage
                    return ToolMessage(
                        content=cached.get('content', ''),
                        tool_call_id=cached.get('tool_call_id', '')
                    )
                return cached

        except Exception as e:
            logger.warning(f'[中间件缓存] 获取失败: {e}')
        return None

    def _save_to_cache(
            self,
            tool_name: str,
            result: Any,
            **kwargs
    ):
        """保存结果到缓存"""
        try:
            key = self._make_key(tool_name, **kwargs)

            # 只使用内存缓存，避免 SqliteStore 事务问题和序列化问题
            # handler 返回的是 ToolMessage，需要提取 content 字符串
            if hasattr(result, 'content'):
                # 保存为可重建的格式
                self._tool_results[key] = {
                    'type': 'toolmessage',
                    'content': result.content,
                    'tool_call_id': getattr(result, 'tool_call_id', '')
                }
                logger.info(f'[中间件缓存] 保存(ToolMessage): {tool_name}')
            else:
                # 直接保存
                self._tool_results[key] = result
                logger.info(f'[中间件缓存] 保存: {tool_name}')

        except Exception as e:
            logger.warning(f'[中间件缓存] 保存失败: {e}')

    def clear_user_cache(self):
        """清除工具调用缓存"""
        if self._tool_results:
            self._tool_results = {}
            logger.info(f'[中间件缓存] 已清除工具调用缓存')

    def _make_key(self, tool_name: str, **kwargs) -> str:
        """生成缓存键"""
        import hashlib
        key_data = f"{tool_name}:{sorted(kwargs.items())}"
        return f"tool_cache:{hashlib.md5(key_data.encode()).hexdigest()}"


    def create_middleware(self):
        """创建中间件"""

        @wrap_tool_call
        def tool_cache_middleware(request, handler):
            # 获取工具名称 - 必须从 request.tool_call["name"] 获取！
            # 这是 LangChain ToolCallRequest 的正确访问方式
            tool_call_dict = getattr(request, 'tool_call', {})
            tool_name = tool_call_dict.get('name') if isinstance(tool_call_dict, dict) else None
            
            # 备用方案：从 BaseTool 获取
            if not tool_name:
                base_tool = getattr(request, 'tool', None)
                if base_tool:
                    tool_name = getattr(base_tool, 'name', None)
            
            # 最后的备用方案
            if not tool_name:
                tool_name = 'unknown'

            # 获取工具参数
            tool_args = tool_call_dict.get('args', {}) if isinstance(tool_call_dict, dict) else {}
            if isinstance(tool_args, str):
                try:
                    tool_args = json.loads(tool_args)
                except:
                    tool_args = {}

            logger.info(f'[中间件] 拦截工具: {tool_name}')

            # 只对RSS工具进行缓存
            cached_tools = ['get_latest_ai_news', 'search_ai_news']

            if tool_name in cached_tools:
                # 检查缓存
                limit = tool_args.get('limit', 15)
                cached = self._get_from_cache(tool_name, limit=limit)

                if cached:
                    logger.info(f'[中间件] 使用缓存: {tool_name}')
                    return cached

                # 执行工具
                result = handler(request)

                # 缓存结果
                if result:
                    self._save_to_cache(tool_name, result, limit=limit)

                return result

            # 其他工具直接执行
            return handler(request)

        return tool_cache_middleware


# 使用示例
def create_tool_cache_middleware_v2(
        cache_store,
        ttl_seconds: int = 600,
):
    """创建工具缓存中间件的工厂函数"""
    middleware = ToolCacheMiddleware(
        cache_store,
        ttl_seconds=ttl_seconds,
    )
    return middleware