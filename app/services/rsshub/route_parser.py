"""
RSSHub routes.json 解析器

功能：
- 解析 RSSHub 的 routes.json 文件
- 将嵌套结构转换为扁平路由列表
- 支持字段映射和防御性编程

输入格式：
{
  "namespace_id": {
    "name": "命名空间名称",
    "url": "域名",
    "categories": ["分类1", "分类2"],
    "lang": "语言",
    "routes": {
      "/route/path": {
        "name": "路由名称",
        "example_path": "/example",
        "description": "描述",
        "parameters": [...],
        "maintainers": [...],
        "features": {...}
      },
      ...
    }
  },
  ...
}

输出格式：
[
  {
    "route_path": "/route/path",
    "route_name": "路由名称",
    "namespace_id": "namespace_id",
    "domain": "域名",
    "example_path": "/example",
    "category": "主分类",
    "categories": "[\"分类1\", \"分类2\"]",
    "lang": "语言",
    "has_params": true,
    "description": "描述",
    "maintainers": "[\"maintainer1\"]",
    "features": "{\"require_puppeteer\": true}",
    "source_file": "routes.json"
  },
  ...
]
"""

import json
import logging
from typing import TypedDict

logger = logging.getLogger(__name__)


# ===== 字段长度约束（与 RSSHubRoute 模型一致）=====
# 修改模型字段长度时必须同步更新此处
FIELD_MAX_LENGTHS: dict[str, int] = {
    "route_path": 500,
    "route_name": 200,
    "namespace_id": 50,
    "domain": 200,
    "example_path": 500,
    "category": 50,
    "lang": 10,
    "source_file": 100,
}


class ParsedRoute(TypedDict):
    """parse_routes_json 返回的单条路由结构"""

    route_path: str
    route_name: str
    namespace_id: str
    domain: str
    example_path: str
    category: str
    categories: str
    lang: str
    has_params: bool
    description: str
    maintainers: str
    features: str
    source_file: str


def parse_routes_json(raw: str, source: str = "routes.json") -> list[ParsedRoute]:
    """
    解析 routes.json 原始字符串为扁平路由列表

    Args:
        raw: routes.json 原始内容（JSON 字符串）
        source: 来源文件名（用于记录）

    Returns:
        list[ParsedRoute]: 扁平化的路由列表，每个 dict 包含完整字段

    Raises:
        不抛出异常，解析失败返回空列表并记录日志
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"routes.json 解析失败（JSON 格式错误）: {e}")
        return []

    if not isinstance(data, dict):
        logger.error(f"routes.json 根节点类型错误，期望 dict，得到 {type(data).__name__}")
        return []

    routes = []

    for namespace_id, ns_value in data.items():
        # 防御性检查：ns_value 必须是 dict
        if not isinstance(ns_value, dict):
            logger.warning(f"命名空间 {namespace_id} 值类型错误，跳过")
            continue

        # 提取命名空间级别字段
        ns_name = ns_value.get("name", "")
        ns_url = ns_value.get("url", namespace_id)  # 降级：用 namespace_id 作为 domain
        ns_categories = ns_value.get("categories", [])
        ns_lang = ns_value.get("lang", "zh-CN")

        # 转换为字符串用于 JSON 存储
        ns_categories_str = json.dumps(ns_categories, ensure_ascii=False) if ns_categories else "[]"

        # 获取路由表
        routes_dict = ns_value.get("routes", {})
        if not isinstance(routes_dict, dict):
            logger.warning(f"命名空间 {namespace_id} 的 routes 字段类型错误，跳过")
            continue

        for route_path, route_value in routes_dict.items():
            # 防御性检查：route_value 必须是 dict
            if not isinstance(route_value, dict):
                logger.warning(f"路由 {route_path} 值类型错误，跳过")
                continue

            # 路由名称（优先使用 route 自带的，否使用 ns 的）
            route_name = route_value.get("name") or ns_name

            # 示例路径
            example_path = route_value.get("example_path") or route_value.get("example")

            # 描述
            description = route_value.get("description", "")

            # 路径参数检测
            has_params = ":" in route_path

            # 主分类（优先使用 route 自带的，否使用 namespace 的第一个）
            category = route_value.get("category")
            if not category and isinstance(ns_categories, list) and len(ns_categories) > 0:
                category = ns_categories[0]

            # 分类列表（优先使用 route 自带的）
            route_categories = route_value.get("categories")
            if not route_categories:
                route_categories = ns_categories
            if isinstance(route_categories, list):
                categories_str = json.dumps(route_categories, ensure_ascii=False)
            else:
                categories_str = "[]"

            # 语言
            lang = route_value.get("lang", ns_lang)

            # 维护者
            maintainers = route_value.get("maintainers", [])
            if isinstance(maintainers, list):
                maintainers_str = json.dumps(maintainers, ensure_ascii=False)
            elif maintainers:
                maintainers_str = json.dumps([maintainers], ensure_ascii=False)
            else:
                maintainers_str = "[]"

            # 特性
            features = route_value.get("features", {})
            if isinstance(features, dict):
                features_str = json.dumps(features, ensure_ascii=False)
            else:
                features_str = "{}"

            # 路由名称（如果为空，使用 route_path）
            if not route_name:
                route_name = route_path

            # 组装扁平路由（带长度截断，防御超长数据写入 DB）
            route_dict = {
                "route_path": route_path[:FIELD_MAX_LENGTHS["route_path"]],
                "route_name": route_name[:FIELD_MAX_LENGTHS["route_name"]],
                "namespace_id": namespace_id[:FIELD_MAX_LENGTHS["namespace_id"]],
                "domain": ns_url[:FIELD_MAX_LENGTHS["domain"]],
                "example_path": (example_path or "")[:FIELD_MAX_LENGTHS["example_path"]],
                "category": (category or "")[:FIELD_MAX_LENGTHS["category"]],
                "categories": categories_str,
                "lang": lang[:FIELD_MAX_LENGTHS["lang"]],
                "has_params": has_params,
                "description": description or "",
                "maintainers": maintainers_str,
                "features": features_str,
                "source_file": source[:FIELD_MAX_LENGTHS["source_file"]],
            }
            routes.append(route_dict)

    logger.info(f"routes.json 解析完成: {len(routes)} 条路由（来源: {source}）")
    return routes


def parse_routes_json_file(file_path: str, source: str = "routes.json") -> list[ParsedRoute]:
    """
    从文件路径读取并解析 routes.json

    Args:
        file_path: routes.json 文件路径
        source: 来源文件名（用于记录）

    Returns:
        list[ParsedRoute]: 扁平化的路由列表
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            raw = f.read()
        return parse_routes_json(raw, source)
    except FileNotFoundError:
        logger.error(f"routes.json 文件不存在: {file_path}")
        return []
    except Exception as e:
        logger.error(f"读取 routes.json 文件失败: {e}")
        return []
