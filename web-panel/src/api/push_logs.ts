/**
 * 推送日志 API
 */
import { request } from './index'

/** 推送日志记录 */
export interface PushLogRecord {
  id: number
  webhook_config_id: number
  webhook_config_name: string | null
  platform: string
  push_type: string
  content: string
  is_success: boolean
  error_message: string | null
  article_id: number | null
  github_repo_id: number | null
  obsidian_file_path: string | null
  git_commit_sha: string | null
  http_status_code: number | null
  pushed_at: string | null
}

/** 推送日志分页响应 */
export interface PaginatedPushLogs {
  items: PushLogRecord[]
  total: number
  page: number
  page_size: number
}

/** 推送日志统计数据 */
export interface PushLogStats {
  total: number
  success_count: number
  fail_count: number
  success_rate: number
  today: number
  by_platform: Record<string, number>
  daily_trend?: Array<{
    date: string
    total: number
    success: number
  }>
}

/** 查询参数 */
export interface PushLogQueryParams {
  page?: number
  page_size?: number
  webhook_config_id?: number
  platform?: string
  push_type?: string
  is_success?: boolean
  start_date?: string
  end_date?: string
}

/**
 * 获取推送日志列表
 */
export async function getPushLogs(
  params?: PushLogQueryParams
): Promise<PaginatedPushLogs> {
  return request.get<PaginatedPushLogs>('/admin/push-logs', { params })
}

/**
 * 获取推送日志统计
 */
export async function getPushLogsStats(params?: {
  days?: number
  platform?: string
}): Promise<PushLogStats> {
  return request.get<PushLogStats>('/admin/push-logs/stats', { params })
}
