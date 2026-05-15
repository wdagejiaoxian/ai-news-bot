#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
更新 routes_static.json 静态副本

从运行中的 RSSHub 容器复制 routes.json 到静态副本目录

用法：
    python scripts/update_routes_static.py

前置条件：
    - RSSHub 容器必须处于运行状态
    - Docker 卷挂载必须配置正确
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATIC_PATH = PROJECT_ROOT / "app" / "services" / "rsshub" / "routes_static.json"
CONTAINER_NAME = "rsshub"
CONTAINER_PATH = "/app/assets/build/routes.json"


def check_container_running() -> bool:
    """检查 RSSHub 容器是否运行"""
    result = subprocess.run(
        ["docker", "ps", "--filter", f"name={CONTAINER_NAME}", "--format", "{{.Names}}"],
        capture_output=True,
        text=True
    )
    return CONTAINER_NAME in result.stdout


def update() -> bool:
    """
    执行更新

    Returns:
        bool: 更新成功返回 True
    """
    print(f"开始更新 routes_static.json...")
    print(f"目标路径: {STATIC_PATH}")

    # 1. 检查容器是否运行
    if not check_container_running():
        print(f"错误: RSSHub 容器未运行，请先启动 RSSHub")
        print(f"提示: docker compose -f docker-compose.rsshub.yml up -d")
        return False

    # 2. 复制文件
    print(f"从容器复制 {CONTAINER_PATH}...")
    result = subprocess.run(
        ["docker", "cp", f"{CONTAINER_NAME}:{CONTAINER_PATH}", str(STATIC_PATH)],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"错误: 复制文件失败")
        print(f"stderr: {result.stderr}")
        return False

    # 3. 验证文件
    try:
        with open(STATIC_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        namespace_count = len(data)
        route_count = sum(len(ns.get("routes", {})) for ns in data.values() if isinstance(ns, dict))

        print(f"更新完成!")
        print(f"  命名空间数: {namespace_count}")
        print(f"  路由数: {route_count}")
        print(f"  更新时间: {datetime.now().isoformat()}")
        print(f"  文件大小: {STATIC_PATH.stat().st_size / 1024 / 1024:.2f} MB")
        return True

    except json.JSONDecodeError as e:
        print(f"错误: JSON 格式无效 - {e}")
        return False
    except Exception as e:
        print(f"错误: {e}")
        return False


if __name__ == "__main__":
    success = update()
    sys.exit(0 if success else 1)
