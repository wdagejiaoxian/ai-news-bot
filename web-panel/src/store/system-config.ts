/**
 * 系统配置 Pinia Store
 *
 * 管理系统配置的状态和操作，供系统设置页面使用。
 * 特性：
 * - 配置项按分类分组（computed）
 * - 修改后本地乐观更新（立即反映到 UI）
 * - 操作失败时 ElMessage 提示
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import type { SystemConfigItem } from '@/types/system-config'
import {
  getSystemConfigs as apiGetSystemConfigs,
  updateSystemConfig as apiUpdateSystemConfig,
  resetSystemConfig as apiResetSystemConfig,
} from '@/api/system-config'

/** 中文分类名称映射（页面中其他组件也会引用） */
export const CATEGORY_LABELS: Record<string, string> = {
  github: 'GitHub',
  scheduler_cleanup: '调度清理',
  score: '评分推送',
  rss: 'RSS 采集',
  process: '内容处理',
  enrich: '内容补全',
  domain_skip: '域名管理',
  rsshub: 'RSSHub',
  vector: '向量搜索',
  timeout: '超时重试',
  wecom: '企业微信',
  general: '通用',
}

export const useSystemConfigStore = defineStore('systemConfig', () => {
  // ========== State ==========

  /** 全部配置项列表 */
  const configs = ref<SystemConfigItem[]>([])
  /** 是否正在加载 */
  const loading = ref(false)
  /** 正在保存的配置 key（组件通过 updatingKey 访问） */
  const updatingKey = ref<string | null>(null)

  // ========== Getters ==========

  /** 已自定义的配置数量 */
  const customizedCount = computed(() =>
    configs.value.filter((c) => c.is_customized).length,
  )

  /** 配置项总数 */
  const totalCount = computed(() => configs.value.length)

  /** 按分类分组的配置项映射 */
  const configsByCategory = computed(() => {
    const map: Record<string, SystemConfigItem[]> = {}
    for (const item of configs.value) {
      const key = item.category
      if (!map[key]) map[key] = []
      map[key].push(item)
    }
    return map
  })

  /** 所有分类的列表（固定顺序） */
  const categories = computed(() => {
    const order = [
      'score', 'rss', 'process', 'enrich', 'domain_skip',
      'scheduler_cleanup', 'github', 'rsshub', 'vector', 'timeout', 'wecom',
    ]
    const keys = new Set(Object.keys(configsByCategory.value))
    return order.filter((c) => keys.has(c))
  })

  // ========== Actions ==========

  /** 从后端加载全部配置（页面 mounted 时调用） */
  async function fetchAll() {
    if (loading.value) return
    loading.value = true
    try {
      const data = await apiGetSystemConfigs()
      configs.value = data.configs || []
    } catch (error: any) {
      ElMessage.error(error?.message || '获取系统配置失败')
      console.error('[SystemConfig] fetchAll failed:', error)
    } finally {
      loading.value = false
    }
  }

  /** 修改单个配置 */
  async function updateByKey(key: string, value: string | number | boolean) {
    updatingKey.value = key
    try {
      const result = await apiUpdateSystemConfig(key, { value })
      const idx = configs.value.findIndex((c) => c.key === key)
      if (idx !== -1) {
        configs.value[idx] = {
          ...configs.value[idx],
          current_value: result.current_value,
          is_customized: true,
        }
      }
      ElMessage.success(`"${key}" 已更新为 ${result.current_value}`)
      return true
    } catch (error: any) {
      ElMessage.error(error?.message || `修改 "${key}" 失败`)
      console.error(`[SystemConfig] updateByKey failed: key=${key}`, error)
      return false
    } finally {
      updatingKey.value = null
    }
  }

  /** 恢复单个配置为默认值 */
  async function resetByKey(key: string) {
    updatingKey.value = key
    try {
      const result = await apiResetSystemConfig(key)
      const idx = configs.value.findIndex((c) => c.key === key)
      if (idx !== -1) {
        configs.value[idx] = {
          ...configs.value[idx],
          current_value: result.current_value,
          is_customized: false,
        }
      }
      ElMessage.success(`"${key}" 已恢复为默认值 ${result.current_value}`)
      return true
    } catch (error: any) {
      ElMessage.error(error?.message || `恢复 "${key}" 默认值失败`)
      console.error(`[SystemConfig] resetByKey failed: key=${key}`, error)
      return false
    } finally {
      updatingKey.value = null
    }
  }

  /** 根据 key 获取单个配置项 */
  function getByKey(key: string): SystemConfigItem | undefined {
    return configs.value.find((c) => c.key === key)
  }

  return {
    configs, loading, updatingKey,
    customizedCount, totalCount, configsByCategory, categories,
    fetchAll, updateByKey, resetByKey, getByKey,
  }
})
