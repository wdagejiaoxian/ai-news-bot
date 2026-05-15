# -*- coding: utf-8 -*-
"""
共享 Pydantic 模型
供 jobs.py 和 configs.py 共用
"""

from typing import Optional

from pydantic import BaseModel, Field


# ==================== 统一响应 ====================


class ApiResponse(BaseModel):
    """统一API响应格式"""
    code: int = 200
    data: Optional[dict] = None
    message: str = "success"


# ==================== 运行时任务模型 ====================


class JobResponse(BaseModel):
    """任务响应"""
    id: str
    name: str
    func: str
    trigger: str
    next_run_time: Optional[str] = None
    last_run_time: Optional[str] = None
    status: str = "active"


class JobListResponse(BaseModel):
    """任务列表响应"""
    items: list[JobResponse]
    total: int


class JobTriggerResponse(BaseModel):
    """任务触发响应"""
    success: bool
    message: str
    job_id: str


# ==================== 任务配置模型 ====================


class TaskConfigUpdate(BaseModel):
    """更新任务配置请求"""
    task_type: Optional[str] = None
    hour: Optional[int] = Field(None, ge=0, le=23)
    minute: Optional[int] = Field(None, ge=0, le=59)
    day_of_week: Optional[int] = Field(None, ge=0, le=6)
    interval_minutes: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None


class TaskConfigResponse(BaseModel):
    """任务配置响应"""
    id: int
    task_name: str
    task_type: str
    hour: Optional[int]
    minute: Optional[int]
    day_of_week: Optional[int]
    interval_minutes: Optional[int]
    is_active: bool
    config_version: int
    next_run: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


class TaskListResponse(BaseModel):
    """任务配置列表响应"""
    items: list[TaskConfigResponse]
    total: int
    page: int
    page_size: int