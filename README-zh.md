# AI News Bot - AI 资讯采集与分析系统

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.135-green)
![Vue 3](https://img.shields.io/badge/Vue_3-3.5-brightgreen)
![License](https://img.shields.io/badge/License-MulanPSL2-red)

AI News Bot 是一个自动化 AI 资讯采集、处理与推送系统。它能够定时从 RSS 订阅源和 GitHub Trending 采集最新 AI 资讯，通过 LLM 进行智能摘要、评分和分类，并通过多种渠道推送给用户。同时集成 RSSHub、向量语义服务、AI 对话 Agent，并配备了完整的 Web 管理面板。

## 功能特性

### 数据采集
- **RSS 订阅源采集** — 支持标准 RSS/Atom 格式，自动解析文章内容，支持增量检测（ETag/Last-Modified）
- **GitHub Trending 采集** — 按编程语言和时间范围（日/周/月）获取热门项目
- **RSSHub 集成** — 自动同步 RSSHub 路由，扩展采集来源。支持服务生命周期管理（自动启动/停止/健康检查）
- **文章内容补全** — 使用 Trafilatura 自动获取文章正文，支持域名黑白名单和动态跳过规则
- **独立采集间隔** — 每个 RSS 源可独立配置采集频率（目前只是简单的在采集rss源定时任务执行时判断具体的rss源是否到了采集时间）

### 智能处理
- **LLM 摘要生成** — 支持多个 LLM Provider（智谱、硅基流动、OpenRouter、ModelScope，后续会扩充）
- **文章价值评分** — 5 维度评分（技术创新性、商业价值、行业影响力、时效性、实用价值），0-100 分
- **批量处理** — 每批 5 篇，批次级并发控制，智能降级（批次失败自动降级到逐篇处理）
- **内容去重** — URL 哈希（BLAKE2b-128）精确去重 + 标题指纹（SHA256）模糊去重 + 向量语义去重
- **关键词提取 & 标签分类** — 自动提取关键词，多维标签体系（领域/技术/主题/影响层级）
- **LLM 并发控制** — 每个 Provider 独立信号量，防止 429 限流

### 向量服务（7 大场景）
- **语义去重（S1）** — 入库前检查语义相似文章
- **LLM 缓存（S2）** — 语义相似查询命中时复用 LLM 结果
- **语义搜索（S3）** — 关键词 + Embedding 混合搜索，带评分权重排序
- **Agent RAG（S4）** — 为 Agent 对话提供检索增强生成（待实现）
- **相似推荐（S5）** — 推荐与指定文章语义相似的内容（阈值 0.80）
- **主题聚类（S6）** — 使用 HDBSCAN 对文章进行无监督主题聚类
- **GitHub 相似（S7）** — 查找语义相似的 GitHub 项目（待实现）

### 多平台推送
- **企业微信** — 群机器人 Webhook + 自建应用消息 + 应用回调消息接收
- **Git** — 自动同步到Git仓库
- **Obsidian** — Local REST API 模式（仅在Obsidian与本项目在同一台主机下运行时支持，若需要远程同步，可考虑Git间接同步Obsidian
- 后续会拓展更多平台
- **内容格式转换** — 长内容 支持转换为 Markdown文件 或者 PDF文件 发送
- **推送失败处理** — 自动统计失败次数，达到阈值自动停用 Webhook

### 定时报告
- **即时推送** — 高分资讯即时推送
- **日报** — 每日 AI 资讯 + GitHub 热门汇总推送
- **周报** — 每周汇总推送
- **LLM 增强** — 可选启用 LLM 翻译和优化报告内容
- **可配置模板** — 支持自定义消息模板（预设模板 + 变量系统）

### AI 对话 Agent
- **企业微信集成** — 通过企业微信自建应用与 AI Agent 对话（消息加解密）
- **多技能系统** — 内置 AI 资讯查询、GitHub 趋势查询、基础对话等技能
- **长期记忆** — 跨会话持久化记忆管理（InMemoryStore / SQLite）
- **工具调用** — 支持查询资讯、GitHub 项目等工具，带工具调用缓存中间件
- **意图识别** — 智能理解用户意图，自动路由到对应技能

### 配置管理
- **双层配置体系** — .env 环境变量基础配置 + 数据库动态配置覆盖
- **配置加密** — AES-256-GCM 加密敏感配置值（API Key 等），ENC 前缀标记
- **Web 面板管理** — 所有数据库配置均可通过 Web 面板在线修改，即时生效

### Web 管理面板
- **数据看板** — ECharts 可视化仪表盘（文章趋势、评分分布、推送统计）
- **文章管理** — 浏览、搜索、筛选、详情查看（支持语义搜索）
- **GitHub 项目管理** — 管理采集到的 GitHub 热门项目，管理需要进行GitHub采集的语言
- **RSS 源管理** — 添加/编辑/删除 RSS 订阅源，支持 RSSHub 路由选择
- **RSSHub帮助** — 用于展示RSSHub、Docker运行状态，对RSSHub进行介绍，对RSSHub支持的路由进行展示，指引Docker的部署
- **我的 LLM 配置** — 管理多 Provider 的 LLM 模型配置
- **Embedding模型配置** — 管理多 Provider 的 Embedding模型配置
- **向量数据库配置** — 管理向量数据库，目前仅支持Chroma，后续会扩展，在此页面可配置不同维度的库，并进行切换
- **Webhook 配置** — 管理推送渠道（企业微信/Telegram/Discord/Obsidian）
- **定时任务管理** — 查看/启停/手动触发定时任务
- **主题聚类可视化** — 查看 HDBSCAN 聚类结果
- **系统设置** — 全局性系统参数配置
- **日志页面** — 操作日志、系统运行日志、推送日志、定时任务执行历史

## 技术栈

| 层级 | 技术 |
|------|------|
| **后端框架** | Python FastAPI + Uvicorn (ASGI) |
| **ORM** | SQLAlchemy 2.0 (async) + aiosqlite |
| **数据库** | SQLite（WAL 模式，30s busy_timeout，Alomic 迁移） |
| **向量数据库** | ChromaDB（适配器模式，预留 Milvus/Qdrant 扩展） |
| **任务调度** | APScheduler 3.11 (AsyncIOScheduler) |
| **AI Agent** | DeepAgents + LangGraph (LangGraph Checkpoint/Store) |
| **LLM 集成** | 智谱 / 硅基流动 / OpenRouter / ModelScope |
| **Embedding** | Ollama / OpenAI / SiliconFlow |
| **RSS 解析** | feedparser + Trafilatura 正文提取 |
| **PDF 生成** | weasyprint + mistune (Markdown→PDF) |
| **内容加密** | AES-256-GCM (pycryptodome) |
| **测试框架** | Pytest + pytest-asyncio |
| **前端框架** | Vue 3.5 + TypeScript |
| **UI 组件** | Element Plus 2.13 |
| **图表** | ECharts 6.0 + vue-echarts |
| **状态管理** | Pinia 3.0 |
| **构建工具** | Vite 8 + vue-tsc |
| **HTTP 客户端** | Axios |
| **部署** | Docker + Docker Compose + Nginx |

## 快速开始

### 环境要求
- Python 3.11+
- Node.js 18+

### 1. 克隆并配置
```bash
git clone <repo-url>
cd ai_news_bot

# 复制配置文件
cp .env.example .env
# 编辑 .env，至少配置 SECRET_KEY 和 WEB_PANEL_PASSWORD
```

### 2. 启动后端
```bash
# 创建虚拟环境
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 启动服务
python -m uvicorn app.main:app --reload --port 8000
```

### 3. 启动前端（可选）
```bash
cd web-panel
npm install
npm run dev
```

### 4. 首次运行
首次启动会自动初始化数据库、创建默认管理员用户。访问以下地址：

- **Web 面板**：http://localhost:3000（默认账号密码见 `.env` 配置）

## 配置说明

### 核心环境变量（.env）

| 配置项 | 说明 | 是否必填 | 默认值 |
|--------|------|---------|-------|
| `SECRET_KEY` | JWT 密钥（≥32 字符） | **必填** | 空 |
| `DATABASE_URL` | 数据库连接 URL | 可选 | sqlite+aiosqlite:///storage/database.db |
| `WEB_PANEL_USERNAME` | Web 面板用户名 | 可选 | admin |
| `WEB_PANEL_PASSWORD` | Web 面板密码 | **必填** | 空 |
| `GITHUB_TOKEN` | GitHub API Token（提高频率限制） | 可选 | 空 |

> **LLM 和 Embedding 的 API Key 等敏感配置已迁移至数据库管理**，通过 Web 面板配置后加密存储，即时生效。

## Docker 部署

```bash
# 完整部署（后端 + 前端 + Nginx）
docker-compose up -d

# 启动可选 RSSHub 服务（二选一）
docker-compose --profile rsshub up -d                # 方式1：Profiles 模式
docker-compose -f docker-compose.rsshub.yml up -d    # 方式2：独立文件

# 启动可选 Ollama 本地 LLM
docker-compose -f docker-compose.ollama.yml up -d

# 仅后端
docker-compose up -d app
```

详细部署步骤参考 `部署步骤参考.md`。

## 项目结构

```
ai_news_bot/
├── app/                            # 后端 Python 应用
│   ├── main.py                     # FastAPI 入口 + 生命周期管理
│   ├── config.py                   # Pydantic Settings 配置管理
│   ├── database.py                 # 异步数据库引擎和会话管理
│   ├── logging.conf                # 日志配置文件
│   ├── api/                        # REST API 路由（22 个路由模块）
│   │   ├── auth.py                 # 登录/Token 刷新
│   │   ├── articles.py             # 文章 CRUD + 语义搜索
│   │   ├── github.py               # GitHub Trending 查询
│   │   ├── rss.py                  # RSS 源 CRUD（含增量检测）
│   │   ├── scheduler/              # 调度器 API（启停/配置）
│   │   ├── webhook/                # Webhook CRUD/测试
│   │   ├── vector_config.py        # 向量服务配置
│   │   ├── llm_config.py           # LLM Provider 配置
│   │   ├── system_config.py        # 系统配置
│   │   └── ...                     # 日志/统计/模板/Obsidian 等
│   ├── models/                     # SQLAlchemy 数据模型
│   ├── services/                   # 业务逻辑层
│   │   ├── fetcher/                # RSS/GitHub/内容采集
│   │   ├── processor/              # LLM 摘要/评分/去重
│   │   ├── notifier/               # 多渠道推送（企微/Telegram/Discord/Obsidian）
│   │   ├── scheduler/              # APScheduler 定时任务
│   │   ├── vector/                 # 向量服务（7 场景编排）
│   │   ├── agentic/                # DeepAgents AI Agent
│   │   └── rsshub/                 # RSSHub 集成管理
│   ├── auth/                       # JWT + HTTP Bearer 认证
│   ├── middleware/                 # RequestID/异常处理/限流
│   └── utils/                      # 加密/审计/日志脱敏/响应工具
├── web-panel/                      # Vue 3 前端应用（14 个页面）
│   └── src/
│       ├── pages/                  # 14+ 页面组件
│       ├── router/                 # Vue Router 配置
│       ├── store/                  # Pinia 状态管理
│       ├── api/                    # Axios API 请求层
│       └── components/             # 20+ 通用组件
├── alembic/                        # 数据库迁移（14 个版本）
├── docker/                         # Docker 构建文件
├── nginx/                          # Nginx 反向代理配置
├── storage/                        # 运行时数据（SQLite/ChromaDB/Agent Memory）
├── tests/                          # Pytest 测试
│   └── unit/
│       ├── api/                    # API 层测试
│       └── services/               # 服务层测试
├── scripts/                        # 工具脚本
├── .env.example                    # 环境变量模板
├── requirements.txt                # Python 依赖
└── pytest.ini                      # Pytest 配置
```

## 定时任务

| 任务 ID | 默认间隔 | 说明 |
|---------|---------|------|
| `fetch_ai_news` | 每 30 分钟 | RSS 订阅源采集（支持增量检测 ETag/Last-Modified） |
| `fetch_github_trending` | 每 60 分钟 | GitHub Trending 热门项目采集 |
| `fetch_weekly_github_trending` | 每周一 | GitHub 周热门采集 |
| `process_pending_content` | 每 5 分钟 | LLM 批量处理待处理文章（摘要/评分/标签/关键词） |
| `send_daily_report` | 每天 09:00 | 日报生成与多渠道推送 |
| `send_weekly_report` | 每周一 09:00 | 周报生成与多渠道推送 |
| `cleanup_low_score_articles` | 每天 03:00 | 自动清理低评分（≤40 分）文章 |
| `cleanup_expired_data` | 每天 03:00 | 清理过期数据 |
| `cluster_topics` | 每天 02:00 | HDBSCAN 无监督主题聚类 |
| `reindex_vectors` | 每周日 04:00 | 向量数据库对账与一致性检查 |

## 评分标准

文章价值评分（0-100）基于以下 5 个维度：

| 分数区间 | 等级 | 说明 |
|---------|------|------|
| 90-100 | 重大突破 | 行业里程碑事件、颠覆性技术 |
| 80-89 | 重要进展 | 头部公司动态、重要产品发布 |
| 70-79 | 值得关注 | 有意义的进展、趋势分析 |
| 60-69 | 常规资讯 | 一般产品更新、行业新闻 |
| 40-59 | 价值有限 | 内容较浅、重复性高 |
| 0-39 | 低价值 | 营销推广、内容质量差 |

**评分维度权重**：技术创新性(25%) | 商业/战略价值(25%) | 行业影响力(20%) | 时效性/稀缺性(20%) | 实用价值(10%)

## 许可证

[Mulan Permissive Software License v2](LICENSE)
