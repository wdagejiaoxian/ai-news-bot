/**
 * 网络状态管理 Composable
 *
 * 功能：
 * - 检测在线/离线状态
 * - 提供重连回调
 * - 持久化网络错误状态
 *
 * @example
 * const { isOnline, isOffline, retry } = useNetworkStatus()
 */
import { ref, onMounted, onUnmounted } from 'vue'

interface NetworkState {
  /** 是否在线 */
  isOnline: boolean
  /** 是否离线（与 isOnline 相反，方便使用） */
  isOffline: boolean
  /** 最后离线时间 */
  lastOfflineAt: Date | null
  /** 连续离线次数（用于判断是否真的断网） */
  offlineCount: number
}

const STORAGE_KEY = 'ai-news-bot-network-errors'

// 全局单例状态
const globalState = {
  isOnline: ref(true),
  isOffline: ref(false),
  lastOfflineAt: ref<Date | null>(null),
  offlineCount: ref(0),
  retryCallbacks: [] as Array<() => void>,
  /** 重试计时器 */
  retryTimer: null as ReturnType<typeof setTimeout> | null,
  /** 是否已初始化 */
  initialized: false,
}

/**
 * 检查是否真的在线（发送一个小请求到后端健康检查）
 */
async function checkReallyOnline(): Promise<boolean> {
  try {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 3000)

    await fetch('/api/health', {
      method: 'HEAD',
      signal: controller.signal,
    })

    clearTimeout(timeoutId)
    return true
  } catch {
    return navigator.onLine
  }
}

/**
 * 网络状态管理 hook（全局单例）
 */
export function useNetworkStatus() {

  /**
   * 处理网络恢复
   */
  function handleOnline() {
    globalState.isOnline.value = true
    globalState.isOffline.value = false

    // 如果连续离线次数超过3次，触发重连回调
    if (globalState.offlineCount.value >= 3) {
      globalState.retryCallbacks.forEach((cb) => {
        try {
          cb()
        } catch (e) {
          console.error('重连回调执行失败:', e)
        }
      })
    }

    // 重置计数
    globalState.offlineCount.value = 0

    // 清除重试计时器
    if (globalState.retryTimer) {
      clearTimeout(globalState.retryTimer)
      globalState.retryTimer = null
    }
  }

  /**
   * 处理网络断开
   */
  function handleOffline() {
    globalState.isOnline.value = false
    globalState.isOffline.value = true
    globalState.lastOfflineAt.value = new Date()
    globalState.offlineCount.value++

    // 延迟5秒后再次检查（避免短暂断网误判）
    if (!globalState.retryTimer) {
      globalState.retryTimer = setTimeout(() => {
        globalState.retryTimer = null
        if (!navigator.onLine) {
          // 仍然离线，保存错误状态
          saveNetworkError()
        }
      }, 5000)
    }
  }

  /**
   * 保存网络错误状态到 localStorage
   */
  function saveNetworkError() {
    const errorState = {
      timestamp: Date.now(),
      offlineCount: globalState.offlineCount.value,
      lastOfflineAt: globalState.lastOfflineAt.value?.toISOString(),
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(errorState))
  }

  /**
   * 获取保存的网络错误状态
   */
  function getSavedNetworkError(): { timestamp: number; offlineCount: number } | null {
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      if (saved) {
        return JSON.parse(saved)
      }
    } catch {
      // ignore
    }
    return null
  }

  /**
   * 清除保存的网络错误状态
   */
  function clearSavedNetworkError() {
    localStorage.removeItem(STORAGE_KEY)
  }

  /**
   * 注册重连回调
   */
  function onRetry(callback: () => void) {
    globalState.retryCallbacks.push(callback)
    return () => {
      const index = globalState.retryCallbacks.indexOf(callback)
      if (index > -1) {
        globalState.retryCallbacks.splice(index, 1)
      }
    }
  }

  /**
   * 手动触发重连
   */
  async function retry() {
    if (navigator.onLine) {
      const reallyOnline = await checkReallyOnline()
      if (reallyOnline) {
        handleOnline()
        return true
      }
    }
    return false
  }

  // 初始化（仅在首次调用时）
  if (!globalState.initialized) {
    globalState.initialized = true

    // 初始化状态
    globalState.isOnline.value = navigator.onLine
    globalState.isOffline.value = !navigator.onLine

    // 如果之前保存了错误状态，恢复离线计数
    const savedError = getSavedNetworkError()
    if (savedError) {
      // 如果保存的错误状态超过30分钟，清除它
      if (Date.now() - savedError.timestamp > 30 * 60 * 1000) {
        clearSavedNetworkError()
      } else {
        globalState.offlineCount.value = savedError.offlineCount || 0
      }
    }

    // 监听网络事件
    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    // 清理函数
    onUnmounted(() => {
      // 注意：全局单例不清除事件监听器，避免重复添加
      // 如果需要清除，可以在组件 unmounted 时手动调用
    })
  }

  return {
    /** 是否在线 */
    isOnline: globalState.isOnline,
    /** 是否离线 */
    isOffline: globalState.isOffline,
    /** 最后离线时间 */
    lastOfflineAt: globalState.lastOfflineAt,
    /** 连续离线次数 */
    offlineCount: globalState.offlineCount,
    /** 注册重连回调 */
    onRetry,
    /** 手动触发重连 */
    retry,
    /** 清除保存的错误状态 */
    clearSavedNetworkError,
  }
}

/**
 * 组合式函数：在组件中使用网络状态
 * 自动在组件 mount 时检查，unmount 时不清理（全局单例）
 */
export function useNetworkStatusOnMount() {
  const { isOnline, isOffline, onRetry } = useNetworkStatus()

  onMounted(async () => {
    // 组件挂载时如果是在线状态，主动探测一下
    if (navigator.onLine) {
      await checkReallyOnline()
    }
  })

  return {
    isOnline,
    isOffline,
    onRetry,
  }
}
