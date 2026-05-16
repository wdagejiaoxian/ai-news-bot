# AI News Bot - AI News Aggregation & Analysis System

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.135-green)
![Vue 3](https://img.shields.io/badge/Vue_3-3.5-brightgreen)
![License](https://img.shields.io/badge/License-MulanPSL2-red)

AI News Bot is an automated AI news aggregation, processing, and delivery system. It periodically fetches the latest AI news from RSS feeds and GitHub Trending, generates intelligent summaries, scores, and categorizes content using LLMs, and delivers updates through multiple channels. The system integrates RSSHub, vector semantic services, AI conversation agents, and comes with a complete web management panel.

## Features

### Data Collection
- **RSS Feed Collection** — Supports standard RSS/Atom format with automatic content parsing and incremental detection (ETag/Last-Modified)
- **GitHub Trending Collection** — Fetches trending projects by programming language and time range (daily/weekly/monthly)
- **RSSHub Integration** — Automatically syncs RSSHub routes to expand collection sources. Includes service lifecycle management (auto-start/stop/health checks)
- **Article Content Completion** — Uses Trafilatura to fetch article body text, with domain whitelist/blacklist and dynamic skip rules
- **Independent Collection Intervals** — Each RSS source can have independently configured collection frequency

### Intelligent Processing
- **LLM Summary Generation** — Supports multiple LLM providers (Zhipu, SiliconFlow, OpenRouter, ModelScope, with more to come)
- **Article Value Scoring** — 5-dimension scoring (Technical Innovation, Business Value, Industry Impact, Timeliness, Practical Value), 0-100 points
- **Batch Processing** — 5 articles per batch with batch-level concurrency control and intelligent degradation (auto-fallback to single-article processing on batch failure)
- **Content Deduplication** — URL hash (BLAKE2b-128) exact deduplication + Title fingerprint (SHA256) fuzzy deduplication + Vector semantic deduplication
- **Keyword Extraction & Tag Classification** — Auto-extract keywords with multi-dimensional tag system (Domain/Technology/Topic/Impact Level)
- **LLM Concurrency Control** — Independent semaphore per provider to prevent 429 rate limiting

### Vector Services (7 Major Scenarios)
- **Semantic Deduplication (S1)** — Check semantically similar articles before insertion
- **LLM Cache (S2)** — Reuse LLM results when semantically similar queries hit
- **Semantic Search (S3)** — Keyword + Embedding hybrid search with scoring weight sorting
- **Agent RAG (S4)** — Provides retrieval-augmented generation for agent conversations (pending implementation)
- **Similar Recommendations (S5)** — Recommend semantically similar content (threshold 0.80)
- **Topic Clustering (S6)** — Unsupervised topic clustering using HDBSCAN
- **GitHub Similar (S7)** — Find semantically similar GitHub projects (pending implementation)

### Multi-Platform Delivery
- **WeCom (Enterprise WeChat)** — Group bot Webhook + Self-built app messages + App callback message receiving
- **Git** — Auto-sync to Git repository
- **Obsidian** — Local REST API mode (only supported when Obsidian and this project run on the same host; for remote sync, consider Git indirect sync to Obsidian)
- More platforms to be added
- **Content Format Conversion** — Long content can be converted to Markdown files or PDF files for delivery
- **Delivery Failure Handling** — Auto-statistics of failures, auto-disable Webhook when threshold is reached

### Scheduled Reports
- **Instant Push** — High-score news instant push
- **Daily Report** — Daily AI news + GitHub trending summary push
- **Weekly Report** — Weekly summary push
- **LLM Enhancement** — Optional LLM translation and report content optimization
- **Configurable Templates** — Custom message templates (preset templates + variable system)

### AI Conversation Agent
- **WeCom Integration** — Chat with AI Agent via WeCom self-built app (message encryption/decryption)
- **Multi-Skill System** — Built-in skills for AI news queries, GitHub trending queries, basic conversation, etc.
- **Long-term Memory** — Cross-session persistent memory management (InMemoryStore / SQLite)
- **Tool Calling** — Support for querying news, GitHub projects, etc., with tool calling cache middleware
- **Intent Recognition** — Intelligent understanding of user intent, auto-routing to corresponding skills

### Configuration Management
- **Dual-layer Configuration System** — .env environment variables base configuration + Database dynamic configuration override
- **Configuration Encryption** — AES-256-GCM encryption for sensitive config values (API Keys, etc.), ENC prefix marking
- **Web Panel Management** — All database configurations can be modified online via Web panel, taking effect immediately

### Web Management Panel
- **Data Dashboard** — ECharts visualization dashboard (article trends, score distribution, push statistics)
- **Article Management** — Browse, search, filter, view details (supports semantic search)
- **GitHub Project Management** — Manage collected GitHub trending projects, manage languages for GitHub collection
- **RSS Source Management** — Add/edit/delete RSS subscriptions, RSSHub route selection
- **RSSHub Help** — Display RSSHub/Docker status, introduce RSSHub, show RSSHub supported routes, guide Docker deployment
- **My LLM Config** — Manage multi-provider LLM model configurations
- **Embedding Model Config** — Manage multi-provider Embedding model configurations
- **Vector Database Config** — Manage vector database, currently only supports Chroma, will expand later. Configure different dimension libraries and switch on this page
- **Webhook Config** — Manage push channels (WeCom/Telegram/Discord/Obsidian)
- **Scheduled Task Management** — View/enable-disable/manually trigger scheduled tasks
- **Topic Clustering Visualization** — View HDBSCAN clustering results
- **System Settings** — Global system parameter configuration
- **Log Page** — Operation logs, system running logs, push logs, scheduled task execution history

## Tech Stack

| Layer | Technology |
|------|------|
| **Backend Framework** | Python FastAPI + Uvicorn (ASGI) |
| **ORM** | SQLAlchemy 2.0 (async) + aiosqlite |
| **Database** | SQLite (WAL mode, 30s busy_timeout, Alomic migration) |
| **Vector Database** | ChromaDB (Adapter pattern,预留 Milvus/Qdrant 扩展) |
| **Task Scheduling** | APScheduler 3.11 (AsyncIOScheduler) |
| **AI Agent** | DeepAgents + LangGraph (LangGraph Checkpoint/Store) |
| **LLM Integration** | Zhipu / SiliconFlow / OpenRouter / ModelScope |
| **Embedding** | Ollama / OpenAI / SiliconFlow |
| **RSS Parsing** | feedparser + Trafilatura content extraction |
| **PDF Generation** | weasyprint + mistune (Markdown→PDF) |
| **Content Encryption** | AES-256-GCM (pycryptodome) |
| **Testing Framework** | Pytest + pytest-asyncio |
| **Frontend Framework** | Vue 3.5 + TypeScript |
| **UI Components** | Element Plus 2.13 |
| **Charts** | ECharts 6.0 + vue-echarts |
| **State Management** | Pinia 3.0 |
| **Build Tool** | Vite 8 + vue-tsc |
| **HTTP Client** | Axios |
| **Deployment** | Docker + Docker Compose + Nginx |

## Quick Start

### Environment Requirements
- Python 3.11+
- Node.js 18+

### 1. Clone and Configure
```bash
git clone <repo-url>
cd ai_news_bot

# Copy configuration file
cp .env.example .env
# Edit .env, configure at least SECRET_KEY and WEB_PANEL_PASSWORD
```

### 2. Start Backend
```bash
# Create virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start service
python -m uvicorn app.main:app --reload --port 8000
```

### 3. Start Frontend (Optional)
```bash
cd web-panel
npm install
npm run dev
```

### 4. First Run
On first startup, database initialization and default admin user creation happen automatically. Access:

- **Web Panel**: http://localhost:3000 (default credentials see .env configuration)

## Configuration Guide

### Core Environment Variables (.env)

| Config Item | Description | Required | Default |
|------------|-------------|---------|---------|
| `SECRET_KEY` | JWT secret (≥32 characters) | **Required** | empty |
| `DATABASE_URL` | Database connection URL | Optional | sqlite+aiosqlite:///storage/database.db |
| `WEB_PANEL_USERNAME` | Web panel username | Optional | admin |
| `WEB_PANEL_PASSWORD` | Web panel password | **Required** | empty |
| `GITHUB_TOKEN` | GitHub API Token (to increase rate limit) | Optional | empty |

> **LLM and Embedding API Keys and other sensitive configurations have been migrated to database management**, configured via Web panel and encrypted for storage, taking effect immediately.

## Docker Deployment

```bash
# Full deployment (backend + frontend + Nginx)
docker-compose up -d

# Start optional RSSHub service (choose one)
docker-compose --profile rsshub up -d                # Method 1: Profiles mode
docker-compose -f docker-compose.rsshub.yml up -d    # Method 2: Separate file

# Start optional Ollama local LLM
docker-compose -f docker-compose.ollama.yml up -d

# Backend only
docker-compose up -d app
```

For detailed deployment steps, refer to `部署步骤参考.md`.

## Project Structure

```
ai_news_bot/
├── app/                            # Backend Python application
│   ├── main.py                     # FastAPI entry + lifecycle management
│   ├── config.py                   # Pydantic Settings configuration management
│   ├── database.py                 # Async database engine and session management
│   ├── logging.conf                # Logging configuration file
│   ├── api/                        # REST API routes (22 route modules)
│   │   ├── auth.py                 # Login/Token refresh
│   │   ├── articles.py             # Article CRUD + Semantic search
│   │   ├── github.py               # GitHub Trending query
│   │   ├── rss.py                  # RSS source CRUD (with incremental detection)
│   │   ├── scheduler/              # Scheduler API (enable-disable/config)
│   │   ├── webhook/                # Webhook CRUD/test
│   │   ├── vector_config.py        # Vector service configuration
│   │   ├── llm_config.py           # LLM Provider configuration
│   │   ├── system_config.py        # System configuration
│   │   └── ...                     # Logs/Statistics/Templates/Obsidian etc.
│   ├── models/                     # SQLAlchemy data models
│   ├── services/                   # Business logic layer
│   │   ├── fetcher/                # RSS/GitHub/Content collection
│   │   ├── processor/              # LLM summary/scoring/deduplication
│   │   ├── notifier/               # Multi-channel push (WeCom/Telegram/Discord/Obsidian)
│   │   ├── scheduler/              # APScheduler scheduled tasks
│   │   ├── vector/                 # Vector service (7-scenario orchestration)
│   │   ├── agentic/                # DeepAgents AI Agent
│   │   └── rsshub/                 # RSSHub integration management
│   ├── auth/                       # JWT + HTTP Bearer authentication
│   ├── middleware/                 # RequestID/Exception handling/Rate limiting
│   └── utils/                      # Encryption/Audit/Log desensitization/Response tools
├── web-panel/                      # Vue 3 frontend application (14 pages)
│   └── src/
│       ├── pages/                  # 14+ page components
│       ├── router/                 # Vue Router configuration
│       ├── store/                  # Pinia state management
│       ├── api/                    # Axios API request layer
│       └── components/             # 20+ common components
├── alembic/                        # Database migrations (14 versions)
├── docker/                         # Docker build files
├── nginx/                          # Nginx reverse proxy configuration
├── storage/                        # Runtime data (SQLite/ChromaDB/Agent Memory)
├── tests/                          # Pytest tests
│   └── unit/
│       ├── api/                    # API layer tests
│       └── services/               # Service layer tests
├── scripts/                        # Utility scripts
├── .env.example                    # Environment variables template
├── requirements.txt                # Python dependencies
└── pytest.ini                      # Pytest configuration
```

## Scheduled Tasks

| Task ID | Default Interval | Description |
|---------|---------|------|
| `fetch_ai_news` | Every 30 minutes | RSS subscription collection (supports incremental detection ETag/Last-Modified) |
| `fetch_github_trending` | Every 60 minutes | GitHub Trending hot projects collection |
| `fetch_weekly_github_trending` | Every Monday | GitHub weekly trending collection |
| `process_pending_content` | Every 5 minutes | LLM batch processing pending articles (summary/scoring/tags/keywords) |
| `send_daily_report` | Daily at 09:00 | Daily report generation and multi-channel push |
| `send_weekly_report` | Every Monday at 09:00 | Weekly report generation and multi-channel push |
| `cleanup_low_score_articles` | Daily at 03:00 | Auto-cleanup low-score articles (≤40 points) |
| `cleanup_expired_data` | Daily at 03:00 | Clean up expired data |
| `cluster_topics` | Daily at 02:00 | HDBSCAN unsupervised topic clustering |
| `reindex_vectors` | Every Sunday at 04:00 | Vector database reconciliation and consistency check |

## Scoring Criteria

Article value scoring (0-100) based on 5 dimensions:

| Score Range | Level | Description |
|-------------|------|------|
| 90-100 | Major Breakthrough | Industry milestone events, disruptive technology |
| 80-89 | Significant Progress | Major company dynamics, important product releases |
| 70-79 | Worth Noting | Meaningful progress, trend analysis |
| 60-69 | Regular News | General product updates, industry news |
| 40-59 | Limited Value | Shallow content, high repetition |
| 0-39 | Low Value | Marketing promotion, poor content quality |

**Scoring Dimension Weights**: Technical Innovation(25%) | Business/Strategic Value(25%) | Industry Impact(20%) | Timeliness/Rarity(20%) | Practical Value(10%)

## License

[Mulan Permissive Software License v2](LICENSE)