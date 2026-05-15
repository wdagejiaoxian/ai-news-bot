import axios, { type AxiosInstance, type AxiosRequestConfig, type AxiosResponse } from 'axios'
import { ElMessage, ElNotification } from 'element-plus'
import router from '@/router'
import type { ApiErrorResponse } from '@/types/api'

// 创建axios实例
const service: AxiosInstance = axios.create({
  baseURL: '/api',
  timeout: 10000,
})

// 防止 401 重试循环标记
let isRefreshing = false
// 存储失败请求队列
let failedQueue: Array<{
  resolve: (token: string) => void
  reject: (error: unknown) => void
}> = []

// 错误类型枚举
enum ErrorType {
  Message = 'message',
  Notification = 'notification',
  None = 'none',
}

// 错误显示配置
const errorDisplayConfig = {
  errorType: ErrorType.Message,
  showAuthError: true,
  showForbiddenError: true,
  showServerError: true,
}

/**
 * 设置全局错误显示配置
 */
export function setGlobalErrorDisplay(options: {
  errorType?: 'message' | 'notification'
  showAuthError?: boolean
  showForbiddenError?: boolean
  showServerError?: boolean
}) {
  if (options.errorType) {
    errorDisplayConfig.errorType = options.errorType === 'notification'
      ? ErrorType.Notification
      : ErrorType.Message
  }
  if (options.showAuthError !== undefined) errorDisplayConfig.showAuthError = options.showAuthError
  if (options.showForbiddenError !== undefined) errorDisplayConfig.showForbiddenError = options.showForbiddenError
  if (options.showServerError !== undefined) errorDisplayConfig.showServerError = options.showServerError
}

/**
 * 显示错误提示
 */
function displayError(message: string, type: ErrorType = ErrorType.Message) {
  if (type === ErrorType.None) return

  if (type === ErrorType.Notification) {
    ElNotification.error({
      title: '请求失败',
      message,
      duration: 4000,
    })
  } else {
    ElMessage.error(message)
  }
}

/**
 * 处理队列中的请求
 */
function processQueue(error: unknown, token: string | null = null) {
  failedQueue.forEach((prom) => {
    if (token) {
      prom.resolve(token)
    } else {
      prom.reject(error)
    }
  })
  failedQueue = []
}

/**
 * 从错误响应中提取错误信息
 */
function extractErrorMessage(response: { status: number, data: ApiErrorResponse }): string {
  const errorData = response.data

  // 优先使用标准错误格式
  if (errorData && typeof errorData.code === 'number' && errorData.message) {
    return errorData.message
  }

  // FastAPI/HTTP 错误格式
  if (errorData && errorData.detail) {
    return errorData.detail
  }

  // 自定义消息字段
  if (errorData && errorData.message) {
    return errorData.message
  }

  // 字段验证错误
  if (errorData && errorData.errors) {
    const firstError = Object.values(errorData.errors)[0]
    if (Array.isArray(firstError) && firstError.length > 0) {
      return firstError[0]
    }
  }

  return '请求失败'
}

// 刷新 Token
async function refreshAccessToken(): Promise<string> {
  const refreshToken = localStorage.getItem('refresh_token')
  if (!refreshToken) {
    throw new Error('No refresh token')
  }

  // 直接用 axios 发请求，避免经过拦截器
  const response = await axios.post('/api/auth/refresh', {
    refresh_token: refreshToken,
  })

  const data = response.data
  if (data.code !== 200) {
    throw new Error(data.message || 'Refresh failed')
  }

  const newAccessToken = data.data.access_token
  localStorage.setItem('access_token', newAccessToken)
  return newAccessToken
}

// 请求拦截器
service.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器 - 统一处理响应格式和错误
service.interceptors.response.use(
  (response: AxiosResponse) => {
    const data = response.data

    // 兼容 wrapped 格式 { code, data, message }
    if (data && typeof data.code === 'number' && 'data' in data) {
      if (data.code !== 200) {
        return Promise.reject(new Error(data.message || '请求失败'))
      }
      return data.data
    }

    // 非 wrapped 格式直接返回
    return data
  },
  async (error) => {
    const { response } = error

    if (response) {
      // 提取错误信息
      const errorMessage = extractErrorMessage(response)

      switch (response.status) {
        case 401:
          // 401: 尝试用 refresh_token 刷新
          if (isRefreshing) {
            // 正在刷新中，将请求加入队列
            return new Promise((resolve, reject) => {
              failedQueue.push({
                resolve: (token: string) => {
                  error.config.headers.Authorization = `Bearer ${token}`
                  resolve(service(error.config))
                },
                reject: (err: unknown) => {
                  reject(err)
                },
              })
            })
          }

          isRefreshing = true

          return refreshAccessToken()
            .then((newToken) => {
              // 刷新成功，重试所有排队的请求
              processQueue(null, newToken)
              error.config.headers.Authorization = `Bearer ${newToken}`
              return service(error.config)
            })
            .catch((refreshError) => {
              // 刷新失败，清空队列并跳转登录
              processQueue(refreshError, null)
              localStorage.removeItem('access_token')
              localStorage.removeItem('refresh_token')
              router.push('/login')
              if (errorDisplayConfig.showAuthError) {
                displayError('登录已过期，请重新登录', errorDisplayConfig.errorType)
              }
              return Promise.reject(refreshError)
            })
            .finally(() => {
              isRefreshing = false
            })

        case 403:
          if (errorDisplayConfig.showForbiddenError) {
            displayError('没有权限访问', errorDisplayConfig.errorType)
          }
          break

        case 404:
          displayError('请求的资源不存在', errorDisplayConfig.errorType)
          break

        case 500:
          if (errorDisplayConfig.showServerError) {
            displayError('服务器错误', errorDisplayConfig.errorType)
          }
          break

        default:
          displayError(errorMessage, errorDisplayConfig.errorType)
      }
    } else {
      // 网络错误（无响应）
      displayError('网络错误，请检查网络连接', errorDisplayConfig.errorType)
    }

    return Promise.reject(error)
  }
)

export default service

// 封装请求方法
export const request = {
  get<T = any>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return service.get(url, config)
  },

  post<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return service.post(url, data, config)
  },

  put<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return service.put(url, data, config)
  },

  delete<T = any>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return service.delete(url, config)
  },
}
