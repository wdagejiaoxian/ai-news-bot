# -*- coding: utf-8 -*-
"""
定时任务配置变更日志记录器

职责：
1. 记录配置变更历史到日志文件
2. 支持查询配置变更日志
3. 集成 operation_logger 写入数据库
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# 确保日志目录存在
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# 配置文件日志
CONFIG_LOG_FILE = LOG_DIR / "scheduler_config.log"


class ConfigLogger:
    """配置变更日志记录器"""

    def __init__(self):
        # 使用独立的 logger
        self.logger = logging.getLogger("scheduler.config")
        self.logger.setLevel(logging.INFO)

        # 避免重复添加 handler
        if not self.logger.handlers:
            # 文件 handler，10MB 滚动，保留 5 个备份
            from logging.handlers import RotatingFileHandler
            file_handler = RotatingFileHandler(
                CONFIG_LOG_FILE, maxBytes=10485760, backupCount=5, encoding="utf-8"
            )
            file_handler.setLevel(logging.INFO)

            # 格式
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            file_handler.setFormatter(formatter)

            self.logger.addHandler(file_handler)

        # 延迟导入 operation_logger，避免循环导入
        self._operation_logger = None

    @property
    def operation_logger(self):
        """延迟获取 operation_logger"""
        if self._operation_logger is None:
            from app.services.operation_logger import operation_logger
            self._operation_logger = operation_logger
        return self._operation_logger

    def record_change(
        self,
        task_name: str,
        old_config: dict,
        new_config: dict,
        changed_by: str = "web_panel",
    ) -> None:
        """
        记录配置变更

        Args:
            task_name: 任务名称
            old_config: 变更前的配置 {"task_type": ..., "hour": ..., ...}
            new_config: 变更后的配置
            changed_by: 变更者 ("web_panel" / "system" / "api")
        """
        # 计算变更字段
        changes = []
        for key in set(list(old_config.keys()) + list(new_config.keys())):
            old_val = old_config.get(key)
            new_val = new_config.get(key)
            if old_val != new_val:
                changes.append({"field": key, "old": old_val, "new": new_val})

        if not changes:
            self.logger.info(f"任务 {task_name} 配置未变更")
            return

        # 构建日志条目
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "task_name": task_name,
            "action": "update",
            "changed_by": changed_by,
            "changes": changes,
            "config_version": new_config.get("config_version"),
        }

        # 写入日志文件
        self.logger.info(f"配置变更: {json.dumps(log_entry, ensure_ascii=False)}")

        # 写入数据库 operation_logs（异步，不阻塞）
        try:
            asyncio.create_task(
                self.operation_logger.log(
                    log_type="config_change",
                    action="update",
                    operator=changed_by,
                    task_name=task_name,
                    detail={
                        "changes": changes,
                        "config_version": new_config.get("config_version"),
                    },
                )
            )
        except Exception as e:
            self.logger.warning(f"写入 operation_logs 失败: {e}")

    def record_init(self, task_name: str, config: dict) -> None:
        """
        记录配置初始化

        Args:
            task_name: 任务名称
            config: 初始配置
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "task_name": task_name,
            "action": "init",
            "changed_by": "system",
            "config": config,
        }

        self.logger.info(f"配置初始化: {json.dumps(log_entry, ensure_ascii=False)}")

        # 写入数据库 operation_logs（异步，不阻塞）
        try:
            asyncio.create_task(
                self.operation_logger.log(
                    log_type="config_change",
                    action="create",
                    operator="system",
                    task_name=task_name,
                    detail={"config": config},
                )
            )
        except Exception as e:
            self.logger.warning(f"写入 operation_logs 失败: {e}")

    def record_reload(self, task_name: str, success: bool, message: str = "") -> None:
        """
        记录热重载

        Args:
            task_name: 任务名称
            success: 是否成功
            message: 消息
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "task_name": task_name,
            "action": "reload",
            "success": success,
            "message": message,
        }

        if success:
            self.logger.info(f"热重载成功: {json.dumps(log_entry, ensure_ascii=False)}")
        else:
            self.logger.error(f"热重载失败: {json.dumps(log_entry, ensure_ascii=False)}")

        # 写入数据库 operation_logs（异步，不阻塞）
        try:
            asyncio.create_task(
                self.operation_logger.log(
                    log_type="config_change",
                    action="reload",
                    operator="system",
                    task_name=task_name,
                    log_level="ERROR" if not success else "INFO",
                    detail={"success": success, "message": message},
                )
            )
        except Exception as e:
            self.logger.warning(f"写入 operation_logs 失败: {e}")

    def get_logs(
        self,
        task_name: Optional[str] = None,
        limit: int = 20,
        since: Optional[datetime] = None,
    ) -> list[dict]:
        """
        获取配置变更日志

        Args:
            task_name: 任务名称（可选，None 表示所有任务）
            limit: 返回条数
            since: 起始时间（可选）

        Returns:
            日志条目列表
        """
        logs = []

        if not CONFIG_LOG_FILE.exists():
            return logs

        try:
            with open(CONFIG_LOG_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    # 解析 JSON
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    # 过滤
                    if task_name and entry.get("task_name") != task_name:
                        continue

                    if since:
                        try:
                            log_time = datetime.fromisoformat(entry.get("timestamp", ""))
                            if log_time < since:
                                continue
                        except ValueError:
                            continue

                    logs.append(entry)

        except Exception as e:
            self.logger.error(f"读取日志失败: {e}")

        # 按时间倒序，返回最近 N 条
        logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return logs[:limit]

    def clear_old_logs(self, days: int = 30) -> int:
        """
        清理旧日志

        Args:
            days: 保留天数

        Returns:
            清理条目数
        """
        if not CONFIG_LOG_FILE.exists():
            return 0

        cutoff = datetime.now() - timedelta(days=days)
        kept_logs = []
        removed_count = 0

        try:
            with open(CONFIG_LOG_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        entry = json.loads(line)
                        log_time = datetime.fromisoformat(entry.get("timestamp", ""))
                        if log_time >= cutoff:
                            kept_logs.append(line)
                        else:
                            removed_count += 1
                    except (json.JSONDecodeError, ValueError):
                        # 保留无法解析的行
                        kept_logs.append(line)

            # 重写文件
            with open(CONFIG_LOG_FILE, "w", encoding="utf-8") as f:
                f.write("\n".join(kept_logs))

            if removed_count > 0:
                self.logger.info(f"已清理 {removed_count} 条过期日志")

        except Exception as e:
            self.logger.error(f"清理日志失败: {e}")

        return removed_count


# 创建全局实例
config_logger = ConfigLogger()
