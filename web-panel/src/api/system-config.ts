/**
 * 系统配置 API 封装
 *
 * 提供系统配置的查询、修改、恢复默认值等 HTTP 接口。
 * 复用全局 Axios 实例（自动携带 JWT Token 和 401 拦截处理）。
 *
 * 注意：Axios 响应拦截器（index.ts:163）已自动解包 ApiResponse.data，
 * 因此泛型参数直接使用内层类型。
 */
import { request } from './index'
import type {
  SystemConfigsData,
  UpdateConfigRequest,
  UpdateConfigResult,
  ResetConfigResult,
} from '@/types/system-config'

/** 获取全部可动态配置的系统配置项 */
export async function getSystemConfigs(): Promise<SystemConfigsData> {
  return request.get<SystemConfigsData>('/system-configs')
}

/** 修改单个系统配置 */
export async function updateSystemConfig(
  key: string,
  data: UpdateConfigRequest,
): Promise<UpdateConfigResult> {
  return request.put<UpdateConfigResult>(`/system-configs/${key}`, data)
}

/** 恢复单个系统配置为 config.py 默认值 */
export async function resetSystemConfig(
  key: string,
): Promise<ResetConfigResult> {
  return request.delete<ResetConfigResult>(
    `/system-configs/${key}/customization`,
  )
}
