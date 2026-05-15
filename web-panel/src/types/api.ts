/**
 * API 响应类型定义
 */

/**
 * 标准 API 响应格式
 */
export interface ApiResponse<T = any> {
  code: number
  data: T
  message?: string
}

/**
 * 分页响应格式
 */
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

/**
 * 操作结果响应
 */
export interface OperationResponse<T = any> {
  success: boolean
  message?: string
  data?: T
}

/**
 * 验证结果
 */
export interface ValidationResult {
  valid: boolean
  errors: string[]
  warnings: string[]
}

/**
 * 错误响应格式
 */
export interface ApiErrorResponse {
  code?: number
  message?: string
  detail?: string
  errors?: Record<string, string[]>
}

/**
 * 请求配置扩展
 */
export interface RequestConfig {
  /** 是否显示全局错误提示 */
  showError?: boolean
  /** 错误提示类型 */
  errorType?: 'message' | 'notification' | 'none'
  /** 是否忽略 401 错误处理（用于刷新Token等特殊接口） */
  ignoreAuthError?: boolean
}

/**
 * 用户信息
 */
export interface UserInfo {
  id: number
  username: string
  is_active: boolean
  role: 'admin' | 'user'
  created_at?: string
}

/**
 * 统计数据
 */
export interface DashboardStats {
  total_articles: number
  total_rss_sources: number
  total_github_projects: number
  total_webhooks: number
  articles_today: number
  articles_this_week: number
  push_success_rate: number
}

/**
 * 文章项
 */
export interface Article {
  id: number
  title: string
  url: string
  summary: string | null
  content: string | null
  score: number
  tags: string[]
  source_name: string
  rss_source_id: number
  published_at: string
  created_at: string
  updated_at: string
}

/**
 * GitHub 项目
 */
export interface GitHubProject {
  id: number
  full_name: string
  url: string
  description: string | null
  stars: number
  stars_today: number
  language: string | null
  language_color: string | null
  rank: number
  fetched_at: string
}

/**
 * RSS 源
 */
export interface RSSSource {
  id: number
  name: string
  url: string
  category: string | null
  is_active: boolean
  fetch_error_count: number
  fetch_interval: number
  article_count: number
  created_at: string
  updated_at: string
}

/**
 * RSS 源表单数据
 */
export interface RSSSourceDTO {
  name: string
  url: string
  category?: string
  fetch_interval?: number
}

/**
 * 调度任务状态
 */
export interface ScheduledJob {
  id: string
  name: string
  func: string
  trigger: string
  next_run_time: string | null
  status: 'active' | 'paused'
}

/**
 * 任务配置
 */
export interface TaskConfig {
  id: number
  task_name: string
  task_type: 'interval' | 'fixed'
  hour: number | null
  minute: number | null
  day_of_week: number | null
  interval_minutes: number | null
  is_active: boolean
  config_version: number
  next_run: string | null
  created_at: string
  updated_at?: string
}

/**
 * 任务配置表单数据
 */
export interface TaskConfigDTO {
  task_type: 'interval' | 'fixed'
  is_active: boolean
  interval_minutes?: number
  hour?: number
  minute?: number
  day_of_week?: number
}

/**
 * 操作日志
 */
export interface OperationLog {
  id: number
  log_type: string
  log_level: string
  task_name: string | null
  operator: string
  action: string
  detail: Record<string, any> | null
  ip_address: string | null
  created_at: string | null
}

/**
 * 操作日志查询参数
 */
export interface LogQueryParams {
  page: number
  page_size: number
  log_type?: string
  action?: string
  start_date?: string
  end_date?: string
}

/**
 * LLM 模型配置
 */
export interface LLMConfig {
  id: number
  provider: string
  api_key: string
  api_base: string
  model_name: string
  is_active: boolean
  max_concurrent: number
  can_use_tool: boolean
  created_at: string
  updated_at: string
}

/**
 * LLM 模型表单数据
 */
export interface LLMConfigDTO {
  provider: string
  model_name: string
  api_key?: string
  api_base?: string
  max_concurrent: number
  is_active: boolean
}

/**
 * 平台选项
 */
export interface PlatformOption {
  platform: string
  name: string
  api_base: string
  models: string[]
}

/**
 * Webhook 配置
 */
export interface Webhook {
  id: number
  name: string
  platform: 'wecom' | 'git' | 'obsidian_local'
  // 推送开关
  push_immediate_enabled: boolean
  push_daily_enabled: boolean
  push_weekly_enabled: boolean
  // 推送阈值
  push_immediate_threshold: number
  push_daily_threshold: number
  push_weekly_threshold: number
  // 推送限制
  push_daily_limit: number
  push_weekly_limit: number
  // 状态
  push_fail_count: number
  push_fail_threshold: number
  is_disabled: boolean
  is_active: boolean
  // 兼容字段
  push_threshold: number
  push_enabled: boolean
  created_at: string
  updated_at?: string
  // Git 配置
  git_repo_url?: string
  git_branch?: string
  git_credential_type?: string
  git_author_name?: string
  git_author_email?: string
  git_daily_folder?: string
  git_weekly_folder?: string
  git_immediate_folder?: string
  // Obsidian Local 配置
  obsidian_api_url?: string
  obsidian_api_key?: string
  obsidian_vault_path?: string
  obsidian_verify_ssl?: boolean
  obsidian_daily_folder?: string
  obsidian_weekly_folder?: string
  obsidian_immediate_folder?: string
  // 模板
  templates?: WebhookTemplate[]
}

/**
 * Webhook 表单数据
 */
export interface WebhookDTO {
  name: string
  platform: 'wecom' | 'git' | 'obsidian_local'
  webhook_key?: string
  // 推送配置
  push_immediate_enabled: boolean
  push_daily_enabled: boolean
  push_weekly_enabled: boolean
  push_immediate_threshold: number
  push_daily_threshold: number
  push_weekly_threshold: number
  push_daily_limit: number
  push_weekly_limit: number
  push_threshold: number
  is_active: boolean
  // Git
  git_repo_url?: string
  git_branch?: string
  git_access_token?: string
  git_credential_type?: string
  git_author_name?: string
  git_author_email?: string
  git_daily_folder?: string
  git_weekly_folder?: string
  git_immediate_folder?: string
  // Obsidian Local
  obsidian_api_url?: string
  obsidian_api_key?: string
  obsidian_vault_path?: string
  obsidian_verify_ssl?: boolean
  obsidian_daily_folder?: string
  obsidian_weekly_folder?: string
  obsidian_immediate_folder?: string
}

/**
 * Webhook 模板
 */
export interface WebhookTemplate {
  id: number
  webhook_config_id: number
  template_type: 'daily' | 'weekly' | 'immediate'
  template_name: string
  template_content: string
  is_active: boolean
  created_at: string
  updated_at: string
}

/**
 * 测试连接结果
 */
export interface TestConnectionResult {
  success: boolean
  message: string
  detail?: string
}

// ==================== RSSHub 类型定义 ====================

/**
 * RSSHub 服务状态
 */
export interface RSSHubStatusResponse {
  status: 'running' | 'stopped' | 'docker_unavailable' | 'starting' | 'error' | 'disabled' | 'unknown'
  docker_available: boolean
  rsshub_url: string
  version: string | null
  routes_count: number | null
  routes_source: 'live' | 'bundled' | null
  checked_at: string | null
  auto_start_enabled: boolean
  message: string | null
  last_error?: string | null  // Docker 检测详细错误原因
}

/**
 * 单条路由项
 */
export interface RouteItem {
  route_path: string
  route_name: string | null
  namespace_id: string | null
  domain: string
  example_path: string | null
  category: string | null
  categories: string  // JSON string
  lang: string
  has_params: boolean
  description: string | null
  maintainers: string  // JSON string
  features: string     // JSON string
  source_file: string
}

/**
 * 可用过滤选项
 */
export interface FiltersMeta {
  languages: string[]
  categories: string[]
}

/**
 * RSSHub 路由列表响应
 */
export interface RSSHubRoutesResponse {
  routes: RouteItem[]
  total: number
  page: number
  page_size: number
  source: 'live' | 'bundled'
  updated_at: string
  available_filters: FiltersMeta
}

/**
 * 路由查询参数
 */
export interface RouteQueryParams {
  page?: number
  page_size?: number
  lang?: string
  category?: string
  keyword?: string
}

/**
 * 路由同步响应
 */
export interface RouteSyncResponse {
  success: boolean
  message: string
  inserted: number
  updated: number
  deleted: number
}
