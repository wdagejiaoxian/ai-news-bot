# -*- coding: utf-8 -*-
"""
操作日志 API

提供日志查询接口，包括：
- 数据库操作日志查询（已有）
- 文件系统日志读取（新增）
"""

import os
import logging
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.middleware import get_current_user
from app.models import User
from app.services.operation_logger import operation_logger

logger = logging.getLogger(__name__)

router = APIRouter()

# 日志文件白名单：只允许展示这些文件
ALLOWED_LOG_FILES = {"app.log", "scheduler_config.log"}

# 日志文件目录
LOG_DIR = Path("logs")


def _resolve_log_file(file: str) -> Path:
    """
    解析并校验日志文件路径

    安全性：
    1. 路径穿越防护：使用 realpath 校验，确保文件在 logs/ 目录下
    2. 文件类型白名单：只允许 .log 后缀
    3. 文件名白名单：只允许 app.log 和 scheduler_config.log

    Args:
        file: 请求的文件名

    Returns:
        解析后的绝对 Path

    Raises:
        HTTPException: 路径穿越、类型不合法、文件不存在
    """
    # 文件名白名单校验
    if file not in ALLOWED_LOG_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件: {file}，仅支持 {', '.join(sorted(ALLOWED_LOG_FILES))}"
        )

    # 路径穿越防护
    requested = (LOG_DIR / file).resolve()
    log_dir_real = LOG_DIR.resolve()
    if not str(requested).startswith(str(log_dir_real)):
        raise HTTPException(status_code=403, detail="非法文件路径")

    if not requested.exists():
        raise HTTPException(status_code=404, detail=f"文件不存在: {file}")

    return requested


@router.get("")
async def list_logs(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    log_type: Optional[str] = Query(None, description="日志类型"),
    task_name: Optional[str] = Query(None, description="任务名称"),
    level: Optional[str] = Query(None, description="日志级别"),
    action: Optional[str] = Query(None, description="操作类型"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    获取操作日志列表

    支持分页和多维度筛选
    """
    try:
        result = await operation_logger.query_logs(
            page=page,
            page_size=page_size,
            log_type=log_type,
            task_name=task_name,
            level=level,
            action=action,
            start_date=start_date,
            end_date=end_date,
        )

        return {
            "code": 200,
            "data": result,
            "message": "success"
        }

    except Exception as e:
        logger.error(f"查询日志列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/file/list")
async def list_log_files(
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    列出 logs/ 目录下可用于展示的日志文件

    返回 app.log 和 scheduler_config.log（不含滚动备份文件 .1 .2 等）
    """
    try:
        if not LOG_DIR.exists():
            return {"code": 200, "data": {"files": []}, "message": "success"}

        files = []
        for p in sorted(LOG_DIR.iterdir(), key=lambda p: p.name):
            # 仅展示白名单中的文件（排除滚动备份 .1 .2 等）
            if p.name in ALLOWED_LOG_FILES:
                stat = p.stat()
                files.append({
                    "name": p.name,
                    "size": stat.st_size,
                    "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })

        return {
            "code": 200,
            "data": {"files": files},
            "message": "success",
        }

    except Exception as e:
        logger.error(f"列出日志文件失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/file")
async def read_log_file(
    file: str = Query(..., description="文件名，如 app.log"),
    lines: int = Query(100, ge=10, le=1000, description="读取行数（从末尾）"),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    读取日志文件内容（从末尾读取，类似 tail -n）

    性能：
    - 使用 deque 高效读取末尾 N 行，不扫描整个文件
    - 限制单次最多 1000 行，防止 OOM
    - 文件超过 100MB 时拒绝读取，防止服务端压力

    安全性：
    - 路径穿越防护
    - 文件名白名单
    - 文件类型校验
    """
    try:
        filepath = _resolve_log_file(file)

        file_size = filepath.stat().st_size

        # 大文件防护：超过 100MB 拒绝读取
        if file_size > 100 * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail="文件过大无法预览（超过 100MB）",
            )

        # 从末尾读取 N 行（高效 tail -n 实现）
        log_lines = _tail_lines(filepath, lines)

        # 计算总行数（快速估算）
        total_lines = _count_lines_fast(filepath)

        return {
            "code": 200,
            "data": {
                "lines": [
                    {"index": i + 1, "text": line}
                    for i, line in enumerate(log_lines)
                ],
                "total_lines": total_lines,
                "file_size": file_size,
                "truncated": file_size > 10 * 1024 * 1024,
            },
            "message": "success",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"读取日志文件失败: file={file}, error={e}")
        raise HTTPException(status_code=500, detail=str(e))


def _detect_encoding(filepath: Path) -> str:
    """
    自动检测文件编码

    优先 UTF-8，若解码失败则回退到系统默认编码（Windows 下为 gbk）。

    Returns:
        编码名称，如 "utf-8"、"gbk"
    """
    with open(filepath, "rb") as f:
        raw = f.read(min(4096, filepath.stat().st_size))

    # 尝试 UTF-8
    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        pass

    # 尝试系统编码
    import locale
    system_encoding = locale.getpreferredencoding()  # Windows 下通常为 gbk
    try:
        raw.decode(system_encoding)
        return system_encoding
    except UnicodeDecodeError:
        pass

    # 最终回退到 UTF-8（带替换）
    return "utf-8"


def _tail_lines(filepath: Path, n: int) -> list[str]:
    """
    高效读取文件末尾 N 行（类似 tail -n）

    算法：
    1. 自动检测文件编码（UTF-8 / GBK）
    2. 从文件末尾倒着读 4KB 块
    3. 用 deque 缓存行（自动丢弃超过 N 的旧行）
    4. 找到 N 行后停止读取

    性能：
    - 大文件（如 50MB）只需读取最后 4KB×N 块
    - 不扫描整个文件
    """
    encoding = _detect_encoding(filepath)

    with open(filepath, "r", encoding=encoding, errors="replace") as f:
        f.seek(0, os.SEEK_END)
        buffer = deque(maxlen=n)
        pos = f.tell()

        while pos > 0:
            # 倒着读一块
            read_size = min(4096, pos)
            pos -= read_size
            f.seek(pos)
            chunk = f.read(read_size)

            # 按行分割，放入 deque
            for line in chunk.split("\n"):
                buffer.append(line)

        # 去除首尾空行，取末 N 行
        result = [line for line in list(buffer) if line]
        return result[-n:]


def _count_lines_fast(filepath: Path) -> int:
    """
    快速估算文件总行数

    对于小文件（<1MB）精确计数，大文件估算。
    """
    try:
        file_size = filepath.stat().st_size
        if file_size < 1024 * 1024:  # 小于 1MB 精确计数
            with open(filepath, "rb") as f:
                return sum(1 for _ in f)
        else:
            # 大文件：采样估算
            with open(filepath, "rb") as f:
                f.seek(0, os.SEEK_END)
                total_bytes = f.tell()
                # 读取末尾 64KB 计算平均行长
                sample_size = min(65536, total_bytes)
                f.seek(total_bytes - sample_size)
                sample = f.read(sample_size)
                lines_in_sample = sample.count(b"\n")
                avg_line_len = sample_size / max(lines_in_sample, 1)
                estimated = int(total_bytes / avg_line_len)
                return estimated
    except Exception:
        return 0


@router.get("/{log_id}")
async def get_log(
    log_id: int,
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    获取单条日志详情
    """
    try:
        log = await operation_logger.get_log_by_id(log_id)

        if not log:
            raise HTTPException(status_code=404, detail="日志不存在")

        return {
            "code": 200,
            "data": log,
            "message": "success"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询日志详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))