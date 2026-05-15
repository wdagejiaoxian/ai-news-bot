# -*- coding: utf-8 -*-
"""
定时任务配置加载器

职责：
1. 从数据库读取定时任务配置
2. 从 config.py 读取默认值
3. 初始化数据库配置
4. 校验配置是否符合约束
"""

import logging
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import db
from app.models import ScheduledTaskConfig, TaskType

logger = logging.getLogger(__name__)


class ConfigLoader:
    """定时任务配置加载器"""

    # 任务模式约束映射
    TASK_MODE_CONSTRAINTS = {
        "fetch_ai_news": {
            "allowed_modes": ["interval"],
            "min_interval": 20,
            "name": "采集AI资讯",
        },
        "process_pending_content": {
            "allowed_modes": ["interval"],
            "min_interval": 20,
            "name": "处理待处理内容",
            "requires_fetch_diff": True,  # 需要与 fetch_ai_news 保持间隔差
        },
        "fetch_github_trending": {
            "allowed_modes": ["interval", "fixed"],
            "name": "采集GitHub热门",
        },
        "fetch_weekly_github_trending": {
            "allowed_modes": ["fixed"],
            "name": "采集GitHub周热门",
        },
        "send_daily_report": {
            "allowed_modes": ["fixed"],
            "name": "发送日报",
        },
        "send_weekly_report": {
            "allowed_modes": ["fixed"],
            "name": "发送周报",
        },
        "cleanup_low_score_articles": {
            "allowed_modes": ["interval", "fixed"],
            "name": "清理低分文章",
        },
        "cleanup_expired_data": {
            "allowed_modes": ["interval", "fixed"],
            "name": "清理过期数据",
        },
        "cluster_topics": {
            "allowed_modes": ["fixed"],
            "name": "主题聚类",
        },
        "reindex_vectors": {
            "allowed_modes": ["fixed"],
            "name": "向量对账",
        },
    }

    # 任务依赖关系配置（M13）
    # key: 任务名称，value: 该任务依赖的任务列表
    TASK_DEPENDENCIES = {
        "process_pending_content": ["fetch_ai_news"],
        "send_daily_report": ["fetch_ai_news", "process_pending_content", "fetch_github_trending"],
        "send_weekly_report": ["fetch_weekly_github_trending", "fetch_ai_news", "process_pending_content"],
    }

    def __init__(self):
        self.settings = get_settings()

    def get_default_configs(self) -> dict:
        """
        从 config.py 读取默认配置

        Returns:
            dict: {task_name: config_dict}
        """
        return {
            "fetch_ai_news": {
                "task_type": "interval",
                "interval_minutes": self.settings.fetch_ai_news_interval,
                "hour": None,
                "minute": None,
                "day_of_week": None,
                "is_active": True,
            },
            "process_pending_content": {
                "task_type": "interval",
                "interval_minutes": self.settings.process_pending_interval,
                "hour": None,
                "minute": None,
                "day_of_week": None,
                "is_active": True,
            },
            "fetch_github_trending": {
                "task_type": "fixed",
                "hour": self.settings.fetch_github_hour,
                "minute": self.settings.default_cron_minute,
                "day_of_week": None,
                "interval_minutes": None,
                "is_active": True,
            },
            "fetch_weekly_github_trending": {
                "task_type": "fixed",
                "hour": self.settings.fetch_weekly_github_hour,
                "minute": self.settings.default_cron_minute,
                "day_of_week": self.settings.weekly_report_day,
                "interval_minutes": None,
                "is_active": True,
            },
            "send_daily_report": {
                "task_type": "fixed",
                "hour": self.settings.daily_report_hour,
                "minute": self.settings.daily_report_minute,
                "day_of_week": None,
                "interval_minutes": None,
                "is_active": True,
            },
            "send_weekly_report": {
                "task_type": "fixed",
                "hour": self.settings.weekly_report_hour,
                "minute": self.settings.default_cron_minute,
                "day_of_week": self.settings.weekly_report_day,
                "interval_minutes": None,
                "is_active": True,
            },
            "cleanup_low_score_articles": {
                "task_type": "fixed",
                "hour": self.settings.cleanup_hour,
                "minute": self.settings.default_cron_minute,
                "day_of_week": None,
                "interval_minutes": None,
                "is_active": True,
            },
            "cleanup_expired_data": {
                "task_type": "fixed",
                "hour": self.settings.cleanup_expired_data_hour,
                "minute": self.settings.default_cron_minute,
                "day_of_week": None,
                "interval_minutes": None,
                "is_active": True,
            },
            "cluster_topics": {
                "task_type": "fixed",
                "hour": self.settings.cluster_cron_hour,
                "minute": self.settings.default_cron_minute,
                "day_of_week": None,
                "interval_minutes": None,
                "is_active": True,
            },
            "reindex_vectors": {
                "task_type": "fixed",
                "hour": self.settings.reindex_cron_hour,
                "minute": self.settings.default_cron_minute,
                "day_of_week": None,
                "interval_minutes": None,
                "is_active": True,
            },
        }

    async def get_task_config(self, task_name: str) -> Optional[ScheduledTaskConfig]:
        """
        获取单个任务配置

        Args:
            task_name: 任务名称

        Returns:
            ScheduledTaskConfig 或 None
        """
        async with db.get_session() as session:
            result = await session.execute(
                select(ScheduledTaskConfig).where(
                    ScheduledTaskConfig.task_name == task_name
                )
            )
            return result.scalar_one_or_none()

    async def get_all_configs(self) -> list[ScheduledTaskConfig]:
        """
        获取所有任务配置

        Returns:
            ScheduledTaskConfig 列表
        """
        async with db.get_session() as session:
            result = await session.execute(
                select(ScheduledTaskConfig).order_by(ScheduledTaskConfig.id)
            )
            configs = list(result.scalars().all())

        # 校验约束关系
        self._validate_config_constraints(configs)

        return configs

    def _validate_config_constraints(self, configs: list[ScheduledTaskConfig]):
        """校验任务配置约束"""
        if not configs:
            return

        config_dict = {c.task_name: c for c in configs}

        # 校验 fetch_ai_news 和 process_pending_content 的间隔关系
        fetch_config = config_dict.get("fetch_ai_news")
        process_config = config_dict.get("process_pending_content")

        if (fetch_config and process_config and
            fetch_config.task_type == "interval" and
            process_config.task_type == "interval"):

            fetch_interval = fetch_config.interval_minutes or 30
            process_interval = process_config.interval_minutes or 20

            if process_interval > fetch_interval - 10:
                logger.warning(
                    f"任务间隔约束失效: process_pending_content({process_interval}min) "
                    f"应 <= fetch_ai_news({fetch_interval}min) - 10min"
                )

    async def initialize_db_configs(self) -> int:
        """
        初始化数据库配置

        策略：
        1. 如果数据库为空，执行全量初始化
        2. 如果数据库有配置，检查缺失的配置并补充（增量同步）

        Returns:
            初始化配置数量（新增）
        """
        async with db.get_session() as session:
            # 获取数据库中所有任务名称
            result = await session.execute(
                select(ScheduledTaskConfig.task_name)
            )
            db_task_names = set(row[0] for row in result.fetchall())

            # 获取默认配置
            default_configs = self.get_default_configs()
            default_task_names = set(default_configs.keys())

            # 计算缺失的配置
            missing_task_names = default_task_names - db_task_names

            if not missing_task_names:
                logger.info(f"数据库配置完整，共 {len(db_task_names)} 条任务配置，无需同步")
                return 0

            # 插入缺失的配置
            for task_name in missing_task_names:
                config = default_configs[task_name]
                task_config = ScheduledTaskConfig(
                    task_name=task_name,
                    task_type=config["task_type"],
                    hour=config.get("hour"),
                    minute=config.get("minute"),
                    day_of_week=config.get("day_of_week"),
                    interval_minutes=config.get("interval_minutes"),
                    is_active=config.get("is_active", True),
                    config_version=1,
                )
                session.add(task_config)
                logger.info(f"同步新任务配置: {task_name}")

            await session.commit()
            logger.info(f"已同步 {len(missing_task_names)} 条新任务配置")
            return len(missing_task_names)

    def validate_config(
        self,
        task_name: str,
        task_type: str,
        interval_minutes: Optional[int] = None,
        fetch_interval: Optional[int] = None,
    ) -> tuple[bool, str]:
        """
        校验配置是否符合约束

        Args:
            task_name: 任务名称
            task_type: 任务类型 ("interval" 或 "fixed")
            interval_minutes: 间隔分钟数（仅 interval 模式）
            fetch_interval: fetch_ai_news 的间隔（用于校验 process_pending_content）

        Returns:
            (is_valid, error_message)
        """
        # 1. 检查任务是否存在
        if task_name not in self.TASK_MODE_CONSTRAINTS:
            return False, f"未知任务: {task_name}"

        constraint = self.TASK_MODE_CONSTRAINTS[task_name]

        # 2. 校验运行模式
        allowed_modes = constraint.get("allowed_modes", [])
        if allowed_modes and task_type not in allowed_modes:
            mode_names: dict[str, str] = {"interval": "间隔触发", "fixed": "固定时间触发"}
            allowed_desc = ", ".join(str(mode_names.get(m, m)) for m in allowed_modes)
            return False, f"任务 {constraint['name']} 不允许使用 {mode_names.get(task_type, task_type)} 模式，允许的模式: {allowed_desc}"

        # 3. 校验最小间隔（仅 interval 模式）
        if task_type == "interval" and interval_minutes is not None:
            min_interval = constraint.get("min_interval", 0)
            if interval_minutes < min_interval:
                return False, f"任务 {constraint['name']} 的间隔不能小于 {min_interval} 分钟"

        # 4. 校验 process_pending_content 与 fetch_ai_news 的间隔关系
        if task_name == "process_pending_content" and task_type == "interval":
            if fetch_interval is not None and interval_minutes is not None:
                max_allowed = fetch_interval - 10
                if interval_minutes > max_allowed:
                    return False, (
                        f"处理待处理任务的间隔时间需要比资讯采集任务小10分钟，"
                        f"当前: 资讯采集={fetch_interval}分钟, 处理待处理={interval_minutes}分钟，"
                        f"处理待处理任务间隔需要 <= {max_allowed} 分钟"
                    )

        return True, ""

    async def validate_and_get_fetch_interval(self, task_name: str) -> Optional[int]:
        """
        获取 fetch_ai_news 的间隔（用于校验其他任务）

        Args:
            task_name: 当前校验的任务名称

        Returns:
            fetch_ai_news 的 interval_minutes 或 None
        """
        if task_name == "process_pending_content":
            fetch_config = await self.get_task_config("fetch_ai_news")
            if fetch_config and fetch_config.task_type == "interval":
                return fetch_config.interval_minutes
        return None

    async def update_config(
        self,
        task_id: int,
        task_type: Optional[str] = None,
        hour: Optional[int] = None,
        minute: Optional[int] = None,
        day_of_week: Optional[int] = None,
        interval_minutes: Optional[int] = None,
        is_active: Optional[bool] = None,
    ) -> tuple[Optional[ScheduledTaskConfig], str]:
        """
        更新任务配置

        Args:
            task_id: 配置ID
            task_type: 任务类型
            hour: 小时
            minute: 分钟
            day_of_week: 星期几
            interval_minutes: 间隔分钟数
            is_active: 是否启用

        Returns:
            (updated_config, error_message)
        """
        async with db.get_session() as session:
            result = await session.execute(
                select(ScheduledTaskConfig).where(ScheduledTaskConfig.id == task_id)
            )
            task_config = result.scalar_one_or_none()

            if not task_config:
                return None, "任务配置不存在"

            task_name = task_config.task_name

            # 获取 fetch_ai_news 的间隔（用于校验）
            fetch_interval = await self.validate_and_get_fetch_interval(task_name)

            # 校验配置
            is_valid, error_msg = self.validate_config(
                task_name=task_name,
                task_type=task_type or task_config.task_type,
                interval_minutes=interval_minutes,
                fetch_interval=fetch_interval,
            )

            if not is_valid:
                return None, error_msg

            # 更新配置
            if task_type is not None:
                task_config.task_type = task_type
            if hour is not None:
                task_config.hour = hour
            if minute is not None:
                task_config.minute = minute
            if day_of_week is not None:
                task_config.day_of_week = day_of_week
            if interval_minutes is not None:
                task_config.interval_minutes = interval_minutes
            if is_active is not None:
                task_config.is_active = is_active

            task_config.config_version += 1

            await session.commit()
            await session.refresh(task_config)

            return task_config, ""

    def get_task_name_mapping(self) -> dict:
        """获取任务ID到任务名称的映射"""
        return {k: v["name"] for k, v in self.TASK_MODE_CONSTRAINTS.items()}


async def validate_task_dependency(
    task_name: str,
    is_active: bool,
) -> tuple[bool, str]:
    """
    校验任务依赖是否满足（M13）

    启用任务时：检查依赖是否都已启用
    禁用任务时：检查是否有其他任务依赖它

    Args:
        task_name: 要操作的任务名称
        is_active: 是否要启用该任务（True=启用，False=禁用）

    Returns:
        (is_valid, error_message)
    """
    if task_name not in ConfigLoader.TASK_DEPENDENCIES:
        # 该任务没有依赖配置，直接放行
        return True, ""

    async with db.get_session() as session:
        if is_active:
            # 启用任务时：检查依赖是否都已启用
            for required_task in ConfigLoader.TASK_DEPENDENCIES[task_name]:
                stmt = select(ScheduledTaskConfig).where(
                    ScheduledTaskConfig.task_name == required_task
                )
                result = await session.execute(stmt)
                config = result.scalar_one_or_none()

                if not config or not config.is_active:
                    logger.warning(
                        f"任务 {task_name} 依赖 {required_task}，"
                        f"但 {required_task} 未启用"
                    )
                    return False, (
                        f"启用任务「{task_name}」需要先启用其依赖任务「{required_task}」"
                    )
        else:
            # 禁用任务时：检查是否有其他任务依赖它
            for dependent, deps in ConfigLoader.TASK_DEPENDENCIES.items():
                if task_name in deps:
                    stmt = select(ScheduledTaskConfig).where(
                        ScheduledTaskConfig.task_name == dependent
                    )
                    result = await session.execute(stmt)
                    config = result.scalar_one_or_none()

                    if config and config.is_active:
                        logger.warning(
                            f"任务 {dependent} 依赖 {task_name}，"
                            f"请先禁用 {dependent}"
                        )
                        return False, (
                            f"任务「{dependent}」依赖「{task_name}」，"
                            f"请先禁用「{dependent}」"
                        )

    return True, ""


# 创建全局实例
config_loader = ConfigLoader()
