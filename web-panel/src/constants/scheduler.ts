/**
 * 任务调度相关常量
 */

/**
 * 只能使用 interval 模式的任务
 */
export const INTERVAL_ONLY_TASKS = ['fetch_ai_news', 'process_pending_content'] as const

/**
 * 只能使用 fixed 模式的任务
 */
export const FIXED_ONLY_TASKS = [
  'fetch_weekly_github_trending',
  'send_daily_report',
  'send_weekly_report',
] as const

/**
 * 需要显示星期选择的任务
 */
export const WEEKLY_TASKS = ['fetch_weekly_github_trending', 'send_weekly_report'] as const

/**
 * 任务类型
 */
export type TaskType = 'interval' | 'fixed'

/**
 * 触发模式映射
 */
export const TASK_TYPE_LABELS: Record<TaskType, string> = {
  interval: '间隔触发',
  fixed: '固定时间',
}

/**
 * 星期名称映射
 */
export const DAY_OF_WEEK_NAMES = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'] as const

/**
 * 最小间隔触发时间（分钟）
 */
export const MIN_INTERVAL_MINUTES = 1

/**
 * 最大间隔触发时间（分钟）
 */
export const MAX_INTERVAL_MINUTES = 1440

/**
 * fetch_ai_news 最小间隔
 */
export const FETCH_AI_NEWS_MIN_INTERVAL = 20

/**
 * 类型推导的任务名称集合
 */
export type IntervalOnlyTask = typeof INTERVAL_ONLY_TASKS[number]
export type FixedOnlyTask = typeof FIXED_ONLY_TASKS[number]
export type WeeklyTask = typeof WEEKLY_TASKS[number]

/**
 * 判断是否为 interval only 任务
 */
export function isIntervalOnlyTask(taskName: string): taskName is IntervalOnlyTask {
  return INTERVAL_ONLY_TASKS.includes(taskName as IntervalOnlyTask)
}

/**
 * 判断是否为 fixed only 任务
 */
export function isFixedOnlyTask(taskName: string): taskName is FixedOnlyTask {
  return FIXED_ONLY_TASKS.includes(taskName as FixedOnlyTask)
}

/**
 * 判断是否为每周任务
 */
export function isWeeklyTask(taskName: string): taskName is WeeklyTask {
  return WEEKLY_TASKS.includes(taskName as WeeklyTask)
}

/**
 * 获取任务允许的触发模式
 */
export function getAllowedTaskTypes(taskName: string): TaskType[] {
  if (isIntervalOnlyTask(taskName)) return ['interval']
  if (isFixedOnlyTask(taskName)) return ['fixed']
  return ['interval', 'fixed']
}

/**
 * 获取任务最小间隔
 */
export function getTaskMinInterval(taskName: string): number {
  if (INTERVAL_ONLY_TASKS.includes(taskName as IntervalOnlyTask)) {
    return FETCH_AI_NEWS_MIN_INTERVAL
  }
  return MIN_INTERVAL_MINUTES
}
