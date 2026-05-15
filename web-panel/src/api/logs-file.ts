/**
 * 系统日志文件 API
 *
 * 提供对 logs/ 目录下日志文件的读取接口
 */
import { request } from './index'

/** 日志文件信息 */
export interface LogFileInfo {
  name: string
  size: number
  mtime: string
}

/** 日志行 */
export interface LogLine {
  index: number
  text: string
}

/** 文件内容响应 */
export interface FileContentResponse {
  lines: LogLine[]
  total_lines: number
  file_size: number
  truncated: boolean
}

/** 文件列表响应 */
export interface FileListResponse {
  files: LogFileInfo[]
}

/**
 * 获取日志文件列表
 *
 * 返回 logs/ 目录下可用于展示的文件（app.log / scheduler_config.log）
 */
export async function getLogFileList(): Promise<FileListResponse> {
  return request.get<FileListResponse>('/admin/logs/file/list')
}

/**
 * 读取日志文件内容（从末尾读取，类似 tail -n）
 *
 * @param params.file  文件名（如 app.log）
 * @param params.lines 读取行数（10~1000，默认 100）
 */
export async function readLogFile(params: {
  file: string
  lines?: number
}): Promise<FileContentResponse> {
  return request.get<FileContentResponse>('/admin/logs/file', { params })
}
