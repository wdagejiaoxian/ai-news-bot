/**
 * RSSHub API 封装
 */

import { request } from './index'
import type {
  RSSHubStatusResponse,
  RSSHubRoutesResponse,
  RouteQueryParams,
  OperationResponse,
  RouteSyncResponse,
} from '@/types/api'

/**
 * RSSHub 状态查询
 */
export async function getRSSHubStatus(): Promise<RSSHubStatusResponse> {
  return request.get<RSSHubStatusResponse>('/rsshub/status')
}

/**
 * RSSHub 路由列表查询
 */
export async function getRSSHubRoutes(
  params: RouteQueryParams
): Promise<RSSHubRoutesResponse> {
  return request.get<RSSHubRoutesResponse>('/rsshub/routes', { params })
}

/**
 * 启动 RSSHub 服务
 */
export async function startRSSHub(): Promise<OperationResponse> {
  return request.post<OperationResponse>('/rsshub/start')
}

/**
 * 停止 RSSHub 服务
 */
export async function stopRSSHub(): Promise<OperationResponse> {
  return request.post<OperationResponse>('/rsshub/stop')
}

/**
 * 更新 RSSHub 镜像并重启
 */
export async function updateRSSHub(): Promise<OperationResponse> {
  return request.post<OperationResponse>('/rsshub/update')
}

/**
 * 手动同步路由
 */
export async function syncRoutes(): Promise<RouteSyncResponse> {
  return request.post<RouteSyncResponse>('/rsshub/sync-routes')
}

/**
 * RSSHub API 对象（便于批量调用）
 */
export const rsshubApi = {
  getStatus: getRSSHubStatus,
  getRoutes: getRSSHubRoutes,
  start: startRSSHub,
  stop: stopRSSHub,
  update: updateRSSHub,
  syncRoutes: syncRoutes,
}