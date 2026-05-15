/**
 * 任务执行历史 API
 */
import { request } from './index'

/** 任务执行记录 */
export interface TaskExecutionRecord {
  id: number
  task_name: string
  status: 'start' | 'success' | 'fail' | 'timeout'
  start_time: string | null
  end_time: string | null
  duration_ms: number | null
  result: string | null
  error_message: string | null
  created_at: string | null
}

/** 分页响应 */
export interface PaginatedHistory {
  items: TaskExecutionRecord[]
  total: number
  page: number
  page_size: number
}

/** 任务统计 */
export interface TaskExecutionStats {
  total_executions: number
  success_count: number
  fail_count: number
  timeout_count: number
  success_rate: number
  avg_duration_ms: number
  max_duration_ms: number
  min_duration_ms: number
  by_task: Array<{
    task_name: string
    total: number
    success: number
    success_rate: number
    avg_duration_ms: number
  }>
}

/** 时长趋势 */
export interface DurationTrend {
  task_name: string
  trend: Array<{
    date: string
    avg_duration_ms: number
    count: number
  }>
}

/** 查询参数 */
export interface HistoryQueryParams {
  page?: number
  page_size?: number
  task_name?: string
  status?: string
  start_date?: string
  end_date?: string
}

/**
 * 获取任务执行历史列表
 */
export async function getTaskExecutionHistory(
  params?: HistoryQueryParams
): Promise<PaginatedHistory> {
  return request.get<PaginatedHistory>(
    '/admin/task-execution-history/history',
    { params }
  )
}

/**
 * 获取任务执行统计
 */
export async function getTaskExecutionStats(
  params?: {
    task_name?: string
    days?: number
  }
): Promise<TaskExecutionStats> {
  return request.get<TaskExecutionStats>(
    '/admin/task-execution-history/history/stats',
    { params }
  )
}

/**
 * 获取任务执行时长趋势
 */
export async function getDurationTrend(
  params: {
    task_name: string
    days?: number
  }
): Promise<DurationTrend> {
  return request.get<DurationTrend>(
    '/admin/task-execution-history/history/trend',
    { params }
  )
}
