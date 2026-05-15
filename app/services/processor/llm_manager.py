# -*- coding: utf-8 -*-
"""
LLM 调用管理器

提供全局的LLM调用锁机制，防止并发调用导致的429错误
"""

import asyncio
import logging
# from typing import Any, Awaitable, Callable
from typing import Any, Awaitable, Callable, Dict, List, Optional
from enum import Enum

from app.config import get_settings

logger = logging.getLogger(__name__)

class LLMProvider(Enum):
    """LLM提供商枚举"""
    ZHIPU = "zhipu"          # 智谱平台
    SILICONFLOW = "siliconflow"  # 硅基流动平台
    # 可扩展其他平台
    OPENROUTER = "openrouter"      # OpenRouter平台
    MODELSCOPE = "modelscope"       # MODELSCOPE平台

class LLMMode(Enum):
    """LLM需求枚举"""
    THINKING_REQUIRED = "thinking_required"    # 需要思考模式的任务（如评分）
    # THINKING_NOT_REQUIRED = "thinking_not_required"  # 不需要思考模式的任务（如摘要、关键词、标签、翻译等）
    USE_TOOL_REQUIRED = "use_tool_required"


class LLMModelConfig:
    """LLM模型配置类"""
    def __init__(
            self,
            provider: LLMProvider,
            model_name: str,
            api_key: str,
            api_base: str,
            can_disable_thinking: bool = True,  # 是否能关闭思考模式
            can_use_tool: bool = True,
            max_concurrent: int = 1
    ):
        self.provider = provider
        self.model_name = model_name
        self.api_key = api_key
        self.api_base = api_base
        # self.can_disable_thinking = can_disable_thinking
        self.can_use_tool = can_use_tool
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)

    def is_available(self) -> bool:
        """检查模型是否可用（API Key是否配置）"""
        return bool(self.api_key)

    # def can_handle_task(self, llm_mode: LLMMode) -> bool:
    #     """检查模型是否能处理特定思考模式需求"""
    #     if llm_mode == LLMMode.THINKING_NOT_REQUIRED:
    #         # 不需要思考模式的任务，只能使用能关闭思考模式的模型
    #         return self.can_disable_thinking
    #     # 需要思考模式的任务，所有模型都能处理（因为都是推理模型）
    #     return True



class LLMManager:
    """
    LLM调用管理器
    
    使用信号量来限制对LLM API的并发访问数量
    """
    
    # def __init__(self, max_concurrent: int = 1):
    #     """
    #     初始化LLM管理器
    #
    #     Args:
    #         max_concurrent: 最大并发调用数量，默认为1以防止429错误
    #     """
    #     self._semaphore = asyncio.Semaphore(max_concurrent)
    #     self._max_concurrent = max_concurrent
    #     logger.info(f"LLM Manager 初始化，最大并发数: {max_concurrent}")
    #
    # async def execute_with_limit(self, func: Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:
    #     """
    #     在并发限制下执行异步函数
    #
    #     Args:
    #         func: 要执行的异步函数
    #         *args: 位置参数
    #         **kwargs: 关键字参数
    #
    #     Returns:
    #         Any: 函数执行结果
    #     """
    #     async with self._semaphore:
    #         logger.debug(f"LLM调用获得许可，当前可用许可数: {self._semaphore._value}")
    #         try:
    #             result = await func(*args, **kwargs)
    #             logger.debug("LLM调用完成，释放许可")
    #             return result
    #         except Exception as e:
    #             logger.error(f"LLM调用异常: {e}")
    #             raise
    #
    # @property
    # def available_permits(self) -> int:
    #     """获取当前可用的许可数量"""
    #     return self._semaphore._value

    def __init__(self):
        self.models: List[LLMModelConfig] = []
        self._model_indices: Dict[LLMMode, int] = {}  # 每种思考模式需求类型的当前模型索引
        self.llm_err_statistic: Dict[str , int] = {}        # 用于统计大模型调用错误次数
        self._db_session_factory = None  # 数据库会话工厂
        logger.info("LLM管理器初始化")

    def set_db_session_factory(self, session_factory):
        """设置数据库会话工厂"""
        self._db_session_factory = session_factory
        logger.info("LLM管理器已设置数据库会话工厂")

    def register_model(
            self,
            provider: LLMProvider,
            model_name: str,
            api_key: str,
            api_base: str,
            # can_disable_thinking: bool = True,
            can_use_tool: bool = True,
            max_concurrent: int = 1
    ) -> None:
        """
        注册一个LLM模型

        Args:
            provider: LLM提供商
            model_name: 模型名称
            api_key: API密钥
            api_base: API基础URL
            # can_disable_thinking: 是否能关闭思考模式
            can_use_tool: 是否能调用工具
            max_concurrent: 最大并发数
        """
        model_config = LLMModelConfig(
            provider=provider,
            model_name=model_name,
            api_key=api_key,
            api_base=api_base,
            # can_disable_thinking=can_disable_thinking,
            can_use_tool=can_use_tool,
            max_concurrent=max_concurrent
        )

        if model_config.is_available():
            self.models.append(model_config)
            logger.info(f"注册LLM模型: {provider.value}/{model_name}")
        else:
            logger.warning(f"跳过注册不可用的LLM模型: {provider.value}/{model_name} (API Key未配置)")

    def register_model_from_db(
            self, provider: str,
            model_name: str,
            api_key: str,
            api_base: str,
            can_disable_thinking: bool,
            can_use_tool: bool,
            max_concurrent: int) -> None:
        """
        从数据库配置注册模型

        Args:
            provider: LLM提供商 (字符串，可能是大写如 "MODELSCOPE")
            model_name: 模型名称
            api_key: API密钥
            api_base: API基础URL
            can_disable_thinking: 是否可关闭思考模式
            can_use_tool: 是否支持工具调用
            max_concurrent: 最大并发数
        """
        # 将 provider 转换为小写以匹配 llm_manager 中的枚举值
        provider_enum = LLMProvider(provider.lower())
        model_config = LLMModelConfig(
            provider=provider_enum,
            model_name=model_name,
            api_key=api_key,
            api_base=api_base,
            can_disable_thinking=can_disable_thinking,
            can_use_tool=can_use_tool,
            max_concurrent=max_concurrent
        )
        self.models.append(model_config)
        logger.info(f"注册LLM模型(从DB): {provider}/{model_name}")

    def unregister_model(self, provider: str, model_name: str) -> bool:
        """
        从管理器移除模型

        Args:
            provider: LLM提供商
            model_name: 模型名称

        Returns:
            是否成功移除
        """
        original_count = len(self.models)
        self.models = [
            m for m in self.models
            if not (m.provider.value == provider and m.model_name == model_name)
        ]
        removed = len(self.models) < original_count
        if removed:
            logger.info(f"移除LLM模型: {provider}/{model_name}")
            # 清除该模型的错误计数
            if model_name in self.llm_err_statistic:
                del self.llm_err_statistic[model_name]
        return removed

    def load_models_from_db(self, db_models: list) -> None:
        """
        批量加载模型（启动时使用）

        Args:
            db_models: 数据库模型列表
        """
        from app.utils.crypto import decrypt_api_key

        for db_model in db_models:
            if db_model.is_active:
                try:
                    api_key = decrypt_api_key(db_model.api_key)
                except Exception:
                    api_key = db_model.api_key

                self.register_model_from_db(
                    provider=db_model.provider,
                    model_name=db_model.model_name,
                    api_key=api_key,
                    api_base=db_model.api_base or "",
                    can_disable_thinking=db_model.can_disable_thinking,
                    can_use_tool=db_model.can_use_tool,
                    max_concurrent=db_model.max_concurrent
                )
        logger.info(f"从数据库加载了 {len([m for m in self.models if m.provider.value == db_models[0].provider if db_models])} 个LLM模型")

    async def _deactivate_model_in_db(self, provider: str, model_name: str):
        """
        将模型 is_active 更新为 False，并同步定时任务状态

        Args:
            provider: LLM提供商
            model_name: 模型名称
        """
        if not self._db_session_factory:
            logger.warning("未设置数据库会话工厂，无法更新模型状态")
            return

        try:
            async with self._db_session_factory() as session:
                from sqlalchemy import update
                from app.models import LLMModel

                stmt = (
                    update(LLMModel)
                    .where(LLMModel.provider == provider, LLMModel.model_name == model_name)
                    .values(is_active=False, consecutive_failures=5)
                )
                await session.execute(stmt)
                await session.commit()
                logger.info(f"数据库模型已禁用: {provider}/{model_name}")
        except Exception as e:
            logger.error(f"更新模型状态失败: {e}")
            return

        # 模型被禁用后，同步定时任务状态
        # 如果没有其他可用模型，定时任务应该被禁用
        try:
            from app.services.scheduler.task_state_manager import TaskStateManager
            await TaskStateManager.check_and_update_task_state()
        except Exception as sync_e:
            logger.error(f"同步定时任务状态失败: {sync_e}")

    def to_select_model(
            self,
            use_tool: bool = False,
            llm_mode: LLMMode = LLMMode.THINKING_REQUIRED,
    ) -> Optional[LLMModelConfig]:
        """
        根据思考模式需求选择合适的模型（使用轮询算法）

        Args:
            llm_mode: LLM需求类型
            use_tool: 是否需要调用工具

        Returns:
            选中的模型配置，如果没有可用模型则返回None
        """
        # 过滤出可用、能处理该思考模式需求和工具调用需求的模型
        if use_tool:
            available_models = [
                model for model in self.models
                if model.is_available() and model.can_use_tool
            ]
        else:
            available_models = [
                model for model in self.models
                # if model.is_available() and model.can_handle_task(llm_mode)
                if model.is_available()
            ]

        if not available_models:
            logger.warning(f"没有可用的LLM模型可以处理思考模式需求: {llm_mode.value}")
            return None

        # 获取该思考模式需求类型的当前索引
        if llm_mode not in self._model_indices:
            self._model_indices[llm_mode] = 0

        # 修正索引越界
        if llm_mode in self._model_indices:
            if self._model_indices[llm_mode] >= len(available_models):
                self._model_indices[llm_mode] = 0  # 重置为0

        # 使用基本轮询算法选择模型
        index = self._model_indices[llm_mode] % len(available_models)
        selected_model = available_models[index]

        # 更新索引为下次选择做准备
        self._model_indices[llm_mode] = (index + 1) % len(available_models)

        logger.debug(
            f"为思考模式需求 {llm_mode.value} 选择模型: "
            f"{selected_model.provider.value}/{selected_model.model_name}"
        )

        return selected_model

    async def execute_with_limit(
            self,
            func: Callable[..., Awaitable[Any]],
            llm_mode: LLMMode = LLMMode.THINKING_REQUIRED,
            ues_tool: bool = False,
            *args,
            **kwargs
    ) -> Any:
        """
        在选定模型的并发限制下执行异步函数

        Args:
            func: 要执行的异步函数
            llm_mode: LLM需求类型，用于选择合适的模型
            ues_tool: 是否需要使用工具
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            Any: 函数执行结果

        Raises:
            Exception: 当所有可用模型都失败时抛出最后一个异常
        """

        # 集中重试机制
        max_retries = get_settings().llm_max_retries
        retry_count = 0
        # last_exception = None

        while retry_count < max_retries:
            # 选择合适的模型
            selected_model = self.to_select_model(
                use_tool=ues_tool,
                llm_mode=llm_mode,
            )


            if not selected_model:
                raise Exception(f"没有可用的LLM模型可以处理思考模式需求: {llm_mode.value}")
            logger.info(f'当前调用的模型：{selected_model.model_name}')

            # 将选中的模型信息传递给func
            kwargs['_selected_model'] = selected_model
            kwargs['_llm_mode'] = llm_mode

            async with selected_model._semaphore:
                logger.debug(
                    f"LLM调用获得许可 [{selected_model.provider.value}/{selected_model.model_name}], "
                    f"思考模式需求: {llm_mode.value}, 当前可用许可数: {selected_model._semaphore._value}"
                )

                try:
                    if selected_model.model_name not in self.llm_err_statistic:
                        self.llm_err_statistic[selected_model.model_name] = 0

                    result = await func(*args, **kwargs)
                    logger.debug(
                        f"LLM调用完成 [{selected_model.provider.value}/{selected_model.model_name}], "
                        f"释放许可, 剩余: {selected_model._semaphore._value}"
                    )
                    self.llm_err_statistic[selected_model.model_name] = 0
                    return result
                except Exception as e:
                    retry_count += 1
                    # last_exception = e

                    # 检查是否是可重试的错误
                    error_str = str(e).lower()
                    is_retryable = any(keyword in error_str for keyword in [
                        '429', 'too many requests', 'rate limit', 'timeout',
                        'connection', 'temporarily unavailable', 'service unavailable'
                    ])

                    if is_retryable and retry_count < max_retries:
                        wait_time = 5 * retry_count  # 递增等待时间
                        logger.warning(
                            f"LLM调用触发可重试错误 [{selected_model.provider.value}/{selected_model.model_name}], "
                            f"错误: {e}, 等待{wait_time}秒后重试 (第{retry_count}/{max_retries}次)"
                        )
                        await asyncio.sleep(wait_time)
                    elif retry_count >= max_retries:
                        logger.error(
                            f"LLM调用失败 [{selected_model.provider.value}/{selected_model.model_name}], "
                            f"已达到最大重试次数 {max_retries}: {e}"
                        )
                        return None
                    else:
                        # # 非可重试错误，直接抛出
                        # raise
                        logger.error(f"未知错误：{e}")
                        self.llm_err_statistic[selected_model.model_name] += 1

                        if self.llm_err_statistic[selected_model.model_name] >= 5:
                            self.models = [model for model in self.models if model.model_name != selected_model.model_name]
                            logger.warning(
                                f"模型{selected_model.model_name}已经连续调用失败5次，已从模型注册列表中删除"
                            )
                            # 同步更新数据库 is_active=False
                            asyncio.create_task(self._deactivate_model_in_db(
                                selected_model.provider.value,
                                selected_model.model_name
                            ))

            # raise last_exception
            return None

    # def close_think_content(
    #         self,
    #         selected_model: LLMModelConfig,
    #         prompt: str,
    #         sys_prompt: str = None,
    # ):
    #     """
    #     当需要关闭模型的思考模式时，需要根据供应商不同填写不同参数
    #     :param selected_model: 选择的模型信息
    #     :param prompt: 提示词
    #     :param sys_prompt: 系统提示词
    #     :return: 返回匹配好的字符串
    #     """
    #     provider = selected_model.provider.value
    #     model_name = selected_model.model_name
    #
    #
    #     format_json = {
    #         "model": model_name,
    #         "messages": [
    #             {"role": "system", "content": sys_prompt},
    #             {"role": "user", "content": prompt}
    #         ],
    #         "temperature": 0.3,
    #     }
    #
    #     if provider == "zhipu":
    #         format_json["thinking"] = {
    #             "type": "disabled"
    #         }
    #     elif provider == "siliconflow" or provider == 'modelscope':
    #         format_json["enable_thinking"] = False
    #     elif provider == "openrouter":
    #         format_json["reasoning"] = {"enabled": True}
    #     return format_json



    def get_model_status(self) -> Dict[str, Any]:
        """
        获取所有注册模型的状态信息

        Returns:
            包含模型状态的字典
        """
        status = {}
        for i, model in enumerate(self.models):
            key = f"{model.provider.value}:{model.model_name}"
            status[key] = {
                "available": model.is_available(),
                # "can_disable_thinking": model.can_disable_thinking,
                "max_concurrent": model.max_concurrent,
                "current_permits": model._semaphore._value if hasattr(model, '_semaphore') else 0
            }
        return status



# 创建全局LLM管理器实例
llm_manager = LLMManager()