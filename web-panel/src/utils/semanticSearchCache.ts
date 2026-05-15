/**
 * 语义搜索前端缓存管理器
 *
 * 功能：
 * - sessionStorage 存储（关闭标签页自动清除）
 * - LRU 策略（超过上限时删除最早创建的缓存）
 * - TTL 自动过期
 * - 容量限制
 *
 * 设计原则：
 * - 单例模式，全局共享缓存实例
 * - LRU 策略：删除最早创建的缓存（而非最近最少使用的）
 * - TTL 过期：每次访问检查，过期自动删除
 * - 异常安全：所有操作都有 try-catch，避免损坏页面功能
 */

/**
 * 缓存条目接口
 * results 使用 any 类型以匹配后端返回的完整数据结构
 */
interface SearchCacheEntry {
  results: any[]
  total: number
  timestamp: number
  keyword: string
  filters: Record<string, any>
  sortWeights: { similarity: number; score: number }
}

class SemanticSearchCache {
  private readonly STORAGE_KEY = 'semantic_search_cache'
  private readonly MAX_ENTRIES = 10
  private readonly TTL = 5 * 60 * 1000 // 5 分钟

  /**
   * 获取缓存键列表
   * 用于跟踪所有缓存项的键，维护 LRU 顺序
   */
  private getCacheKeys(): string[] {
    try {
      const keys = sessionStorage.getItem(`${this.STORAGE_KEY}_keys`)
      return keys ? JSON.parse(keys) : []
    } catch {
      console.warn('[SemanticSearchCache] 读取缓存键列表失败')
      return []
    }
  }

  /**
   * 保存缓存键列表
   */
  private saveCacheKeys(keys: string[]): void {
    try {
      sessionStorage.setItem(`${this.STORAGE_KEY}_keys`, JSON.stringify(keys))
    } catch (e) {
      console.warn('[SemanticSearchCache] 保存缓存键列表失败:', e)
    }
  }

  /**
   * 生成缓存键
   * 使用简单的哈希算法，基于 keyword、filters、sortWeights 生成唯一键
   */
  private generateKey(
    keyword: string,
    filters: Record<string, any>,
    sortWeights: { similarity: number; score: number }
  ): string {
    const keyData = JSON.stringify({ keyword, filters, sortWeights })
    // 简单哈希函数（与后端 MD5 不同，但足够用于缓存键）
    let hash = 0
    for (let i = 0; i < keyData.length; i++) {
      const char = keyData.charCodeAt(i)
      hash = ((hash << 5) - hash) + char
      hash = hash & hash // 转换为 32 位整数
    }
    return `${this.STORAGE_KEY}_${Math.abs(hash).toString(36)}`
  }

  /**
   * 获取缓存
   *
   * @returns 缓存项，如果不存在或已过期返回 null
   */
  get(
    keyword: string,
    filters: Record<string, any>,
    sortWeights: { similarity: number; score: number }
  ): SearchCacheEntry | null {
    try {
      const key = this.generateKey(keyword, filters, sortWeights)
      const cached = sessionStorage.getItem(key)

      if (!cached) {
        console.debug('[SemanticSearchCache] 缓存未命中:', key.substring(0, 30))
        return null
      }

      const entry: SearchCacheEntry = JSON.parse(cached)

      // 检查 TTL
      if (Date.now() - entry.timestamp > this.TTL) {
        console.debug('[SemanticSearchCache] 缓存已过期:', key.substring(0, 30))
        this.remove(key)
        return null
      }

      console.debug('[SemanticSearchCache] 缓存命中:', key.substring(0, 30))
      return entry
    } catch (e) {
      console.warn('[SemanticSearchCache] 读取缓存失败:', e)
      return null
    }
  }

  /**
   * 设置缓存
   * 如果已存在则更新，如果超过容量则 LRU 删除
   */
  set(
    keyword: string,
    filters: Record<string, any>,
    sortWeights: { similarity: number; score: number },
    results: any[],
    total: number
  ): void {
    try {
      const key = this.generateKey(keyword, filters, sortWeights)
      const keys = this.getCacheKeys()

      // 如果已存在，先删除（更新时需要重新排序）
      const existingIndex = keys.indexOf(key)
      if (existingIndex !== -1) {
        keys.splice(existingIndex, 1)
      }

      // 添加到列表末尾（最新）
      keys.push(key)

      // 如果超过上限，删除最早的（LRU）
      while (keys.length > this.MAX_ENTRIES) {
        const oldestKey = keys.shift()
        if (oldestKey) {
          sessionStorage.removeItem(oldestKey)
          console.debug('[SemanticSearchCache] LRU 删除缓存:', oldestKey.substring(0, 30))
        }
      }

      // 保存缓存
      const entry: SearchCacheEntry = {
        results,
        total,
        timestamp: Date.now(),
        keyword,
        filters,
        sortWeights,
      }

      sessionStorage.setItem(key, JSON.stringify(entry))
      this.saveCacheKeys(keys)
      console.debug('[SemanticSearchCache] 缓存写入:', key.substring(0, 30), '条数:', results.length)
    } catch (e) {
      console.warn('[SemanticSearchCache] 写入缓存失败:', e)
    }
  }

  /**
   * 删除单个缓存项
   */
  private remove(key: string): void {
    try {
      sessionStorage.removeItem(key)
      const keys = this.getCacheKeys().filter(k => k !== key)
      this.saveCacheKeys(keys)
    } catch (e) {
      console.warn('[SemanticSearchCache] 删除缓存失败:', e)
    }
  }

  /**
   * 清除所有缓存
   */
  clear(): void {
    try {
      const keys = this.getCacheKeys()
      keys.forEach(key => sessionStorage.removeItem(key))
      sessionStorage.removeItem(`${this.STORAGE_KEY}_keys`)
      console.info('[SemanticSearchCache] 已清除所有缓存')
    } catch (e) {
      console.warn('[SemanticSearchCache] 清除缓存失败:', e)
    }
  }

  /**
   * 获取缓存统计信息
   */
  getStats(): { count: number; maxCount: number } {
    return {
      count: this.getCacheKeys().length,
      maxCount: this.MAX_ENTRIES,
    }
  }
}

// 导出单例
export const semanticSearchCache = new SemanticSearchCache()
