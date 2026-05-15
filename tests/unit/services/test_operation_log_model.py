# -*- coding: utf-8 -*-
"""
OperationLog 模型和枚举单元测试

测试 app.models 中的 LogType, LogLevel, LogAction 枚举和 OperationLog 模型
"""
import pytest
import pytest_asyncio
from datetime import datetime
from sqlalchemy import select

from app.models import OperationLog, LogType, LogLevel, LogAction, Base
from sqlalchemy.ext.asyncio import AsyncSession


class TestLogTypeEnum:
    """测试 LogType 枚举"""

    def should_have_config_change_value(self):
        """should_have_config_change_value"""
        assert LogType.CONFIG_CHANGE.value == "config_change"

    def should_have_task_exec_value(self):
        """should_have_task_exec_value"""
        assert LogType.TASK_EXEC.value == "task_exec"

    def should_have_system_value(self):
        """should_have_system_value"""
        assert LogType.SYSTEM.value == "system"

    def should_be_string_enum(self):
        """should_be_string_enum - 验证是字符串枚举，可直接与字符串比较"""
        # LogType 继承 str, Enum，所以可以直接与字符串比较
        assert LogType.CONFIG_CHANGE == "config_change"
        assert LogType.CONFIG_CHANGE.value == "config_change"
        assert isinstance(LogType.CONFIG_CHANGE.value, str)


class TestLogLevelEnum:
    """测试 LogLevel 枚举"""

    def should_have_info_value(self):
        """should_have_info_value"""
        assert LogLevel.INFO.value == "INFO"

    def should_have_warning_value(self):
        """should_have_warning_value"""
        assert LogLevel.WARNING.value == "WARNING"

    def should_have_error_value(self):
        """should_have_error_value"""
        assert LogLevel.ERROR.value == "ERROR"

    def should_be_string_enum(self):
        """should_be_string_enum - 验证是字符串枚举可直接比较"""
        level = LogLevel.INFO
        assert level == "INFO"
        assert level.value == "INFO"


class TestLogActionEnum:
    """测试 LogAction 枚举"""

    def should_have_create_value(self):
        """should_have_create_value"""
        assert LogAction.CREATE.value == "create"

    def should_have_update_value(self):
        """should_have_update_value"""
        assert LogAction.UPDATE.value == "update"

    def should_have_delete_value(self):
        """should_have_delete_value"""
        assert LogAction.DELETE.value == "delete"

    def should_have_reload_value(self):
        """should_have_reload_value"""
        assert LogAction.RELOAD.value == "reload"

    def should_have_start_value(self):
        """should_have_start_value"""
        assert LogAction.START.value == "start"

    def should_have_success_value(self):
        """should_have_success_value"""
        assert LogAction.SUCCESS.value == "success"

    def should_have_fail_value(self):
        """should_have_fail_value"""
        assert LogAction.FAIL.value == "fail"


class TestOperationLogModel:
    """测试 OperationLog 模型"""

    @pytest.mark.asyncio
    async def should_create_operation_log_with_all_fields(self, db_session: AsyncSession):
        """should_create_operation_log_with_all_fields - 测试创建完整的日志记录"""
        log = OperationLog(
            log_type=LogType.TASK_EXEC.value,
            log_level=LogLevel.INFO.value,
            task_name="fetch_ai_news",
            operator="scheduler",
            action=LogAction.SUCCESS.value,
            detail='{"duration_ms": 1000}',
            ip_address="192.168.1.1",
        )

        db_session.add(log)
        await db_session.commit()
        await db_session.refresh(log)

        assert log.id is not None
        assert log.log_type == "task_exec"
        assert log.log_level == "INFO"
        assert log.task_name == "fetch_ai_news"
        assert log.operator == "scheduler"
        assert log.action == "success"
        assert log.detail == '{"duration_ms": 1000}'
        assert log.ip_address == "192.168.1.1"
        assert log.created_at is not None

    @pytest.mark.asyncio
    async def should_create_operation_log_with_minimal_fields(self, db_session: AsyncSession):
        """should_create_operation_log_with_minimal_fields - 测试创建最小字段日志"""
        log = OperationLog(
            log_type=LogType.SYSTEM.value,
            operator="system",
            action=LogAction.START.value,
        )

        db_session.add(log)
        await db_session.commit()
        await db_session.refresh(log)

        assert log.id is not None
        assert log.log_type == "system"
        assert log.operator == "system"
        assert log.action == "start"
        # 可选字段应该为 None
        assert log.task_name is None
        assert log.log_level == LogLevel.INFO.value  # 有默认值
        assert log.detail is None
        assert log.ip_address is None

    @pytest.mark.asyncio
    async def should_query_operation_logs_by_type(self, db_session: AsyncSession):
        """should_query_operation_logs_by_type - 测试按类型查询"""
        # 创建多种类型的日志
        log1 = OperationLog(log_type=LogType.TASK_EXEC.value, operator="sys", action="start")
        log2 = OperationLog(log_type=LogType.CONFIG_CHANGE.value, operator="sys", action="update")
        log3 = OperationLog(log_type=LogType.TASK_EXEC.value, operator="sys", action="success")

        db_session.add_all([log1, log2, log3])
        await db_session.commit()

        result = await db_session.execute(
            select(OperationLog).where(OperationLog.log_type == LogType.TASK_EXEC.value)
        )
        logs = result.scalars().all()

        assert len(logs) == 2
        for log in logs:
            assert log.log_type == LogType.TASK_EXEC.value

    @pytest.mark.asyncio
    async def should_query_operation_logs_by_action(self, db_session: AsyncSession):
        """should_query_operation_logs_by_action - 测试按操作类型查询"""
        log1 = OperationLog(log_type="task", operator="sys", action="start")
        log2 = OperationLog(log_type="task", operator="sys", action="success")
        log3 = OperationLog(log_type="task", operator="sys", action="fail")

        db_session.add_all([log1, log2, log3])
        await db_session.commit()

        result = await db_session.execute(
            select(OperationLog).where(OperationLog.action == "success")
        )
        logs = result.scalars().all()

        assert len(logs) == 1
        assert logs[0].action == "success"

    @pytest.mark.asyncio
    async def should_query_operation_logs_by_task_name(self, db_session: AsyncSession):
        """should_query_operation_logs_by_task_name - 测试按任务名称查询"""
        log1 = OperationLog(log_type="task", operator="sys", action="start", task_name="fetch_news")
        log2 = OperationLog(log_type="task", operator="sys", action="start", task_name="fetch_github")
        log3 = OperationLog(log_type="task", operator="sys", action="start", task_name="fetch_news")

        db_session.add_all([log1, log2, log3])
        await db_session.commit()

        result = await db_session.execute(
            select(OperationLog).where(OperationLog.task_name == "fetch_news")
        )
        logs = result.scalars().all()

        assert len(logs) == 2
        for log in logs:
            assert log.task_name == "fetch_news"

    @pytest.mark.asyncio
    async def should_order_operation_logs_by_created_at_desc(self, db_session: AsyncSession):
        """should_order_operation_logs_by_created_at_desc - 测试按创建时间倒序"""
        import time

        log1 = OperationLog(log_type="t", operator="s", action="a")
        db_session.add(log1)
        await db_session.commit()
        time.sleep(0.01)  # 确保时间戳不同

        log2 = OperationLog(log_type="t", operator="s", action="b")
        db_session.add(log2)
        await db_session.commit()

        result = await db_session.execute(
            select(OperationLog).order_by(OperationLog.created_at.desc())
        )
        logs = result.scalars().all()

        # 最新的应该在前面
        assert logs[0].id > logs[1].id

    @pytest.mark.asyncio
    async def should_filter_by_log_level(self, db_session: AsyncSession):
        """should_filter_by_log_level - 测试按日志级别筛选"""
        log1 = OperationLog(log_type="t", operator="s", action="a", log_level="INFO")
        log2 = OperationLog(log_type="t", operator="s", action="b", log_level="ERROR")
        log3 = OperationLog(log_type="t", operator="s", action="c", log_level="WARNING")

        db_session.add_all([log1, log2, log3])
        await db_session.commit()

        result = await db_session.execute(
            select(OperationLog).where(OperationLog.log_level == "ERROR")
        )
        logs = result.scalars().all()

        assert len(logs) == 1
        assert logs[0].log_level == "ERROR"

    @pytest.mark.asyncio
    async def should_support_pagination(self, db_session: AsyncSession):
        """should_support_pagination - 测试分页支持"""
        # 创建 10 条日志
        logs = [
            OperationLog(log_type="t", operator="s", action=f"action_{i}")
            for i in range(10)
        ]
        db_session.add_all(logs)
        await db_session.commit()

        # 查询第一页，每页 3 条
        result = await db_session.execute(
            select(OperationLog)
            .order_by(OperationLog.id)
            .offset(0)
            .limit(3)
        )
        page1 = result.scalars().all()

        assert len(page1) == 3
        assert page1[0].action == "action_0"
        assert page1[1].action == "action_1"
        assert page1[2].action == "action_2"

    @pytest.mark.asyncio
    async def should_handle_null_detail_as_none(self, db_session: AsyncSession):
        """should_handle_null_detail_as_none - 测试 detail 为 NULL"""
        log = OperationLog(log_type="t", operator="s", action="a", detail=None)

        db_session.add(log)
        await db_session.commit()
        await db_session.refresh(log)

        assert log.detail is None

    @pytest.mark.asyncio
    async def should_handle_json_detail_string(self, db_session: AsyncSession):
        """should_handle_json_detail_string - 测试 JSON 格式的 detail"""
        import json

        detail_data = {"duration_ms": 1500, "articles_count": 25, "errors": []}
        log = OperationLog(
            log_type="t",
            operator="s",
            action="success",
            detail=json.dumps(detail_data, ensure_ascii=False)
        )

        db_session.add(log)
        await db_session.commit()
        await db_session.refresh(log)

        # 验证存储的是 JSON 字符串
        assert log.detail is not None
        parsed = json.loads(log.detail)
        assert parsed["duration_ms"] == 1500
        assert parsed["articles_count"] == 25

    @pytest.mark.asyncio
    async def should_repr_return_meaningful_string(self, db_session: AsyncSession):
        """should_repr_return_meaningful_string - 测试 __repr__ 方法"""
        log = OperationLog(log_type="task_exec", operator="sys", action="success")

        db_session.add(log)
        await db_session.commit()

        repr_str = repr(log)

        assert "OperationLog" in repr_str
        assert "task_exec" in repr_str
        assert "success" in repr_str
