# -*- coding: utf-8 -*-
"""
定时任务状态管理器

根据 LLM 和 Webhook 配置状态，自动启用/禁用所有定时任务
"""

import logging
from sqlalchemy import select, update, func

from app.database import db
from app.models import LLMModel, WebhookConfig, ScheduledTaskConfig

logger = logging.getLogger(__name__)


class TaskStateManager:
    """定时任务状态管理器"""

    @staticmethod
    async def check_and_update_task_state() -> tuple[bool, int]:
        """
        检查LLM和Webhook配置状态，更新定时任务状态并重载调度器

        检查逻辑：
        - LLM表有 is_active=True 的记录 → LLM可用
        - Webhook表有 is_active=True 的记录 → Webhook可用
        - LLM可用 且 Webhook可用 → 启用所有定时任务
        - 否则 → 禁用所有定时任务

        Returns:
            tuple[bool, int]: (all_enabled, changed_count)
        """
        # 1. 检查 LLM 是否有 is_active=True 的记录
        has_llm = await TaskStateManager._has_active_llm()

        # 2. 检查 Webhook 是否有 is_active=True 的记录
        has_webhook = await TaskStateManager._has_active_webhook()

        # 3. 判断是否应该全部启用
        should_enable = has_llm and has_webhook

        # 4. 批量更新定时任务状态
        if should_enable:
            changed_count = await TaskStateManager.enable_all_tasks()
            logger.info(
                f"LLM和Webhook配置齐全，启用所有定时任务 "
                f"(has_llm={has_llm}, has_webhook={has_webhook}, changed={changed_count})"
            )
        else:
            changed_count = await TaskStateManager.disable_all_tasks()
            logger.info(
                f"LLM或Webhook配置不完整，禁用所有定时任务 "
                f"(has_llm={has_llm}, has_webhook={has_webhook}, changed={changed_count})"
            )

        # 5. 重载调度器以使变更生效
        if changed_count > 0:
            await TaskStateManager.reload_scheduler()

        return should_enable, changed_count

    @staticmethod
    async def _has_active_llm() -> bool:
        """检查是否存在启用的LLM模型"""
        async with db.get_session() as session:
            result = await session.scalar(
                select(func.count(LLMModel.id))
                .where(LLMModel.is_active == True)
            )
            return (result or 0) > 0

    @staticmethod
    async def _has_active_webhook() -> bool:
        """检查是否存在启用的Webhook"""
        async with db.get_session() as session:
            result = await session.scalar(
                select(func.count(WebhookConfig.id))
                .where(WebhookConfig.is_active == True)
            )
            return (result or 0) > 0

    @staticmethod
    async def enable_all_tasks() -> int:
        """启用所有定时任务，返回变更的任务数量"""
        async with db.get_session() as session:
            # 先查询当前启用状态
            from sqlalchemy import select, func
            current_active_count = await session.scalar(
                select(func.count(ScheduledTaskConfig.id))
                .where(ScheduledTaskConfig.is_active == True)
            ) or 0

            # 再查询总数
            total_count = await session.scalar(
                select(func.count(ScheduledTaskConfig.id))
            ) or 0

            # 如果全部已经是启用状态，直接返回0
            if current_active_count == total_count:
                return 0

            # 执行更新
            stmt = (
                update(ScheduledTaskConfig)
                .where(ScheduledTaskConfig.is_active == False)
                .values(is_active=True)
            )
            await session.execute(stmt)
            await session.commit()

            # 返回变更数量
            return total_count - current_active_count

    @staticmethod
    async def disable_all_tasks() -> int:
        """禁用所有定时任务，返回变更的任务数量"""
        async with db.get_session() as session:
            # 先查询当前启用状态
            from sqlalchemy import select, func
            current_active_count = await session.scalar(
                select(func.count(ScheduledTaskConfig.id))
                .where(ScheduledTaskConfig.is_active == True)
            ) or 0

            # 如果全部已经禁用，直接返回0
            if current_active_count == 0:
                return 0

            # 执行更新
            stmt = (
                update(ScheduledTaskConfig)
                .where(ScheduledTaskConfig.is_active == True)
                .values(is_active=False)
            )
            await session.execute(stmt)
            await session.commit()

            # 返回变更数量
            return current_active_count

    @staticmethod
    async def reload_scheduler():
        """通知调度器重新注册任务"""
        from app.services.scheduler.jobs import scheduler

        # 调用 scheduler 的热重载方法
        result = scheduler.reload_jobs()
        logger.info(f"调度器热重载完成: {result}")
        return result

    @staticmethod
    async def sync_and_reload() -> dict:
        """
        执行完整的状态同步并重载调度器

        包含以下步骤：
        1. 检查并更新任务状态
        2. 重新加载调度器任务

        Returns:
            dict: 包含状态同步和重载结果
        """
        # 1. 检查并更新状态
        all_enabled, changed_count = await TaskStateManager.check_and_update_task_state()

        # 2. 重新加载调度器
        reload_result = await TaskStateManager.reload_scheduler()

        return {
            "all_enabled": all_enabled,
            "changed_count": changed_count,
            "reload_result": reload_result,
        }
