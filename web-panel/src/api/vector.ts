/**
 * 向量服务 API 封装
 *
 * 对应后端 API:
 * - /api/vector/* (向量配置)
 * - /api/articles/search/semantic (语义搜索)
 * - /api/articles/{id}/similar (相似推荐)
 * - /api/stats/vector (向量统计)
 * - /api/stats/clusters (聚类统计)
 */

import { request } from './index'
import type {
  EmbeddingModel,
  EmbeddingModelCreate,
  EmbeddingModelUpdate,
  VectorDBConfig,
  VectorDBConfigFull,
  VectorDBConfigListResponse,
  VectorDBConfigCreate,
  VectorDBConfigUpdate,
  VectorStats,
  EmbeddingHealth,
  EmbeddingTestResult,
  SearchResult,
  ClusterTopic,
  VectorSystemStats,
  EmbeddingModelsResponse,
  EmbeddingModelCreateResponse,
  EmbeddingModelUpdateResponse,
  ClusterDetailResponse,
  ClusterTrend,
} from '@/types/vector'

/**
 * 获取所有 Embedding 模型配置
 */
export const getEmbeddingModels = () =>
  request.get<EmbeddingModelsResponse>('/vector/embedding-models')

/**
 * 创建 Embedding 模型配置
 * @returns 新创建的模型信息（含 dimension_warning 维度调整提示）
 */
export const createEmbeddingModel = (data: EmbeddingModelCreate) =>
  request.post<EmbeddingModelCreateResponse>('/vector/embedding-models', data)

/**
 * 更新 Embedding 模型配置
 * @returns 更新后的模型信息（含 dimension_warning 维度调整提示）
 */
export const updateEmbeddingModel = (id: number, data: EmbeddingModelUpdate) =>
  request.put<EmbeddingModelUpdateResponse>('/vector/embedding-models/' + id, data)

/**
 * 删除 Embedding 模型配置
 */
export const deleteEmbeddingModel = (id: number) =>
  request.delete<void>('/vector/embedding-models/' + id)

/**
 * 测试 Embedding 模型连通性
 */
export const testEmbeddingModel = (id: number) =>
  request.post<EmbeddingTestResult>('/vector/embedding-models/' + id + '/test')

/**
 * 获取 Embedding 服务健康状态
 */
export const getEmbeddingHealth = () =>
  request.get<EmbeddingHealth>('/vector/embedding-models/health')

/**
 * 获取向量数据库配置
 */
export const getVectorDBConfig = () =>
  request.get<VectorDBConfig>('/vector/db/config')

/**
 * 更新向量数据库配置
 */
export const updateVectorDBConfig = (data: VectorDBConfigUpdate) =>
  request.put<void>('/vector/db/config', data)

/**
 * 获取向量数据库健康状态
 */
export const getVectorDBHealth = () =>
  request.get<{ available: boolean }>('/vector/db/health')

/**
 * 获取向量数据库统计信息
 */
export const getVectorDBStats = () =>
  request.get<VectorStats>('/vector/db/stats')

/**
 * 获取所有向量数据库配置（多配置列表）
 */
export const getVectorDBConfigs = () =>
  request.get<VectorDBConfigListResponse>('/vector/db/configs')

/**
 * 创建向量数据库配置
 */
export const createVectorDBConfig = (data: VectorDBConfigCreate) =>
  request.post<VectorDBConfigFull>('/vector/db/configs', data)

/**
 * 激活向量数据库配置
 */
export const activateVectorDBConfig = (id: number) =>
  request.put<VectorDBConfigFull>('/vector/db/configs/' + id + '/activate')

/**
 * 删除向量数据库配置
 */
export const deleteVectorDBConfig = (id: number) =>
  request.delete<{ deleted: boolean; collections_removed: boolean }>('/vector/db/configs/' + id)

/**
 * 语义搜索文章
 * @param q 搜索词
 * @param limit 返回数量，默认 20
 */
export const semanticSearch = (q: string, limit = 20) =>
  request.get<SearchResult[]>('/articles/search/semantic', {
    params: { q, limit },
  })

/**
 * 获取相似文章推荐
 * @param articleId 文章 ID
 * @param limit 推荐数量，默认 5
 */
export const getSimilarArticles = (articleId: number, limit = 5) =>
  request.get<SearchResult[]>('/articles/' + articleId + '/similar', {
    params: { limit },
  })

/**
 * 获取向量系统统计（24h 缓存命中率等）
 */
export const getVectorStats = () =>
  request.get<VectorSystemStats>('/stats/vector')

/**
 * 获取聚类主题列表
 * @param days 分析天数，默认 7
 */
export const getClusterStats = (days = 7) =>
  request.get<ClusterTopic[]>('/stats/clusters', { params: { days } })

/**
 * 获取聚类详情（含文章列表）
 * @param clusterId 聚类ID
 */
export const getClusterDetail = (clusterId: number) =>
  request.get<ClusterDetailResponse>('/stats/clusters/' + clusterId + '/articles')

/**
 * 获取聚类趋势数据（用于图表）
 * @param days 分析天数，默认 30
 * @note 后端暂未实现此 API，保留函数以备后用
 */
export const getClusterTrend = (days = 30) =>
  request.get<ClusterTrend[]>('/stats/clusters/trend', { params: { days } })

/**
 * 向量服务 API 对象（便于批量调用）
 */
export const vectorApi = {
  // Embedding 模型
  getModels: getEmbeddingModels,
  createModel: createEmbeddingModel,
  updateModel: updateEmbeddingModel,
  deleteModel: deleteEmbeddingModel,
  testModel: testEmbeddingModel,
  getHealth: getEmbeddingHealth,

  // 向量数据库
  getDBConfig: getVectorDBConfig,
  updateDBConfig: updateVectorDBConfig,
  getDBHealth: getVectorDBHealth,
  getDBStats: getVectorDBStats,

  // 向量数据库（多配置）
  getDBConfigs: getVectorDBConfigs,
  createDBConfig: createVectorDBConfig,
  activateDBConfig: activateVectorDBConfig,
  deleteDBConfig: deleteVectorDBConfig,

  // 搜索与推荐
  semanticSearch,
  getSimilarArticles,

  // 统计
  getVectorStats,
  getClusterStats,
  getClusterDetail,
  getClusterTrend,
}
