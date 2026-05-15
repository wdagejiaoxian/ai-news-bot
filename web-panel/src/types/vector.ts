/**
 * 向量服务 TypeScript 类型定义
 *
 * 对应后端 API:
 * - /api/vector/* (向量配置)
 * - /api/articles/search/semantic (语义搜索)
 * - /api/articles/{id}/similar (相似推荐)
 * - /api/stats/vector (向量统计)
 * - /api/stats/clusters (聚类统计)
 */

/**
 * Embedding 模型（列表/详情响应）
 */
export interface EmbeddingModel {
  id: number
  provider: string
  model_name: string
  display_name: string
  api_base: string | null
  dimension: number
  max_batch_size: number
  max_concurrency: number
  priority: number
  is_enabled: boolean
  consecutive_failures: number
  created_at: string | null
}

/**
 * Embedding 模型创建表单
 */
export interface EmbeddingModelCreate {
  provider: string
  model_name: string
  display_name?: string
  api_key?: string
  api_base?: string
  dimension?: number
  max_batch_size?: number
  max_concurrency?: number
  priority?: number
  is_enabled?: boolean
}

/**
 * Embedding 模型更新表单
 */
export interface EmbeddingModelUpdate {
  display_name?: string
  api_key?: string
  api_base?: string
  max_batch_size?: number
  max_concurrency?: number
  priority?: number
  is_enabled?: boolean
}

/**
 * 向量数据库配置（详情响应）
 */
export interface VectorDBConfig {
  id: number
  db_type: string
  connection_string: string
  collection_prefix: string
  dimension: number // 新增
  is_active: boolean
  is_default: boolean // 新增
}

/**
 * 向量数据库配置（完整格式，含 collection 统计）
 * 用于 /api/vector/db/configs 列表响应
 */
export interface VectorDBConfigFull {
  id: number
  db_type: string
  connection_string: string
  dimension: number
  is_active: boolean
  is_default: boolean
  collection_names: {
    articles: string
    github_repos: string
  }
  articles_count: number
  github_count: number
  created_at: string | null
}

/**
 * 向量数据库配置列表响应
 */
export interface VectorDBConfigListResponse {
  configs: VectorDBConfigFull[]
}

/**
 * 向量数据库配置创建请求
 */
export interface VectorDBConfigCreate {
  db_type: string
  connection_string: string
  dimension: number
}

/**
 * 向量数据库配置更新表单
 */
export interface VectorDBConfigUpdate {
  db_type?: string
  connection_string?: string
  is_active?: boolean
}

/**
 * 向量数据库统计信息
 */
export interface VectorStats {
  available: boolean
  articles_count?: number
  github_count?: number
  total?: number
}

/**
 * Embedding 服务健康状态（扩展，含维度兼容性）
 */
export interface EmbeddingHealth {
  available: boolean
  active_models: number
  dimension: number
  active_dimension: number | null // 新增
  models_compatibility: {
    // 新增
    compatible_count: number
    incompatible_count: number
    details: ModelCompatibilityItem[]
  }
}

/**
 * 模型维度兼容性详情项
 */
export interface ModelCompatibilityItem {
  id: number
  name: string
  dimension: number
  compatible: boolean
}

/**
 * Embedding 模型连通性测试结果
 */
export interface EmbeddingTestResult {
  healthy: boolean
  message?: string
}

/**
 * 语义搜索结果项
 */
export interface SearchResult {
  article_id: number
  title: string
  summary: string | null
  similarity: number
  score: number | null
  published_at: string | null
  url: string
  source_name: string | null
}

/**
 * 主题聚类项
 */
export interface ClusterTopic {
  id: number
  date: string
  keywords: string[]
  article_count: number
  avg_score: number
  hotness: number
  is_emerging: boolean
}

/**
 * 聚类中的文章
 */
export interface ClusterArticle {
  id: number
  title: string
  summary: string | null
  score: number | null
  url: string
  source: string | null
  source_name: string
}

/**
 * 聚类详情响应（含文章列表）
 */
export interface ClusterDetailResponse {
  cluster: ClusterTopic
  articles: ClusterArticle[]
}

/**
 * 聚类趋势数据（用于图表）
 * 注意：后端暂未提供此 API，保留此类型以备后用
 */
export interface ClusterTrend {
  date: string
  total_clusters: number
  emerging_count: number
  avg_hotness: number
}

/**
 * 向量系统统计（/stats/vector 响应）
 */
export interface VectorSystemStats {
  vector_db_available: boolean
  active_embedding_models: number
  cache_hit_rate_24h: number
  total_processed_24h: number
  cache_hits_24h: number
}

/**
 * Embedding 模型列表响应（list_embedding_models）
 */
export interface EmbeddingModelsResponse {
  models: EmbeddingModel[]
}

/**
 * Embedding 模型创建响应
 */
export interface EmbeddingModelCreateResponse {
  id: number
  provider: string
  model_name: string
  dimension: number
  dimension_warning?: string
}

/**
 * Embedding 模型更新响应
 */
export interface EmbeddingModelUpdateResponse {
  id: number
  provider: string
  model_name: string
  dimension: number
  dimension_warning?: string
}
