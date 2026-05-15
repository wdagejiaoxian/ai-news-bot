/**
 * 系统配置 TypeScript 类型定义
 *
 * 对应后端 app/api/system_config.py 中的响应格式。
 * 字段命名使用 snake_case，与后端返回的 JSON key 一致。
 * Axios 响应拦截器仅解包 ApiResponse.data，不做大小写转换。
 */

/** 配置项分类 */
export type ConfigCategory =
  | 'github'
  | 'scheduler_cleanup'
  | 'score'
  | 'rss'
  | 'process'
  | 'enrich'
  | 'domain_skip'
  | 'rsshub'
  | 'vector'
  | 'timeout'
  | 'wecom'

/** 值类型标记 */
export type ConfigValueType = 'str' | 'int' | 'float' | 'bool'

/** 单个配置项（字段与后端 JSON 响应对齐） */
export interface SystemConfigItem {
  key: string
  current_value: string | number | boolean
  default_value: string | number | boolean
  value_type: ConfigValueType
  category: ConfigCategory
  is_encrypted: boolean
  is_customized: boolean
  updated_at: string | null
}

/** 配置列表查询响应 */
export interface SystemConfigsData {
  configs: SystemConfigItem[]
  total: number
  customized_count: number
}

/** 修改配置请求体 */
export interface UpdateConfigRequest {
  value: string | number | boolean
}

/** 修改配置的返回结果 */
export interface UpdateConfigResult {
  key: string
  current_value: string | number | boolean
  previous_value: string | number | boolean
  message: string
}

/** 恢复默认值的返回结果 */
export interface ResetConfigResult {
  key: string
  current_value: string | number | boolean
  message: string
}
