/**
 * RSS 源 API
 */
import { request } from './index'

/**
 * RSS 源状态接口
 */
export interface RssSourceStatus {
  has_sources: boolean  // 是否有RSS源（任意状态）
  has_active_sources: boolean  // 是否有活跃RSS源
  total_count: number  // 总源数量
  active_count: number  // 活跃源数量
}

/**
 * RSS 源响应接口（与后端 RSSSourceResponse 对应）
 */
export interface RssSource {
  id: number
  name: string
  url: string
  category: string | null
  source_type: string
  is_active: boolean
  rsshub_unavailable: boolean
  fetch_error_count: number
  fetch_interval: number
  last_fetched_at: string | null
  article_count: number
  last_modified: string | null
  etag: string | null
  created_at: string | null
  updated_at: string | null
}

/**
 * RSS 源列表响应
 */
export interface RssSourceListResponse {
  items: RssSource[]
  total: number
}

/**
 * RSS 源创建请求
 */
export interface RssSourceCreateRequest {
  name: string
  url: string
  category?: string
  source_type?: string
  is_active?: boolean
  fetch_interval?: number
}

/**
 * RSS 源更新请求
 */
export interface RssSourceUpdateRequest {
  name?: string
  url?: string
  category?: string
  source_type?: string
  is_active?: boolean
  fetch_interval?: number
}

/**
 * RSS 源校验响应
 */
export interface RssSourceValidateResponse {
  valid: boolean
  message: string
  feed_title?: string
  entry_count: number
}

/**
 * RSS 源自动发现响应
 */
export interface RssSourceDiscoverResponse {
  direct_rss: Array<{ url: string }>
  rsshub_routes: string[]
  source_type?: string
  message: string
  rsshub_hint?: string
}

/**
 * 获取 RSS 源状态
 * 用于前端判断是否显示"无活跃源"警告
 */
export async function getRssSourceStatus(): Promise<RssSourceStatus> {
  return request.get<RssSourceStatus>('/rss-sources/status')
}

/**
 * 获取 RSS 源列表
 */
export async function getRssSources(params?: {
  category?: string
  is_active?: boolean
}): Promise<RssSourceListResponse> {
  return request.get<RssSourceListResponse>('/rss-sources/', { params })
}

/**
 * 获取单个 RSS 源详情
 */
export async function getRssSource(sourceId: number): Promise<RssSource> {
  return request.get<RssSource>(`/rss-sources/${sourceId}`)
}

/**
 * 校验 RSS 源
 */
export async function validateRssSource(
  url: string,
  sourceType: string = 'standard'
): Promise<RssSourceValidateResponse> {
  return request.post<RssSourceValidateResponse>('/rss-sources/validate', {
    url,
    source_type: sourceType,
  })
}

/**
 * 自动发现 RSS 源
 */
export async function discoverRssSource(
  url: string
): Promise<RssSourceDiscoverResponse> {
  return request.post<RssSourceDiscoverResponse>('/rss-sources/discover', {
    url,
  })
}

/**
 * 创建 RSS 源
 */
export async function createRssSource(
  data: RssSourceCreateRequest
): Promise<RssSource> {
  return request.post<RssSource>('/rss-sources/', data)
}

/**
 * 更新 RSS 源
 */
export async function updateRssSource(
  sourceId: number,
  data: RssSourceUpdateRequest
): Promise<RssSource> {
  return request.put<RssSource>(`/rss-sources/${sourceId}`, data)
}

/**
 * 删除 RSS 源
 */
export async function deleteRssSource(sourceId: number): Promise<void> {
  return request.delete(`/rss-sources/${sourceId}`)
}