/**
 * 聚类列表 Composable
 *
 * 提供聚类数据的获取、筛选、排序逻辑
 */

import { ref, computed, watch } from 'vue'
import { getClusterStats } from '@/api/vector'
import type { ClusterTopic } from '@/types/vector'

export function useClusters() {
  const clusters = ref<ClusterTopic[]>([])
  const loading = ref(false)
  const days = ref(7)
  const sortBy = ref<'hotness' | 'date' | 'article_count'>('hotness')
  const onlyEmerging = ref(false)

  const fetchClusters = async () => {
    loading.value = true
    try {
      const data = await getClusterStats(days.value)
      clusters.value = data || []
    } catch (error) {
      console.error('获取聚类数据失败:', error)
      clusters.value = []
    } finally {
      loading.value = false
    }
  }

  const filteredClusters = computed(() => {
    let result = [...clusters.value]

    // 筛选新兴话题
    if (onlyEmerging.value) {
      result = result.filter(c => c.is_emerging)
    }

    // 排序
    switch (sortBy.value) {
      case 'hotness':
        result.sort((a, b) => b.hotness - a.hotness)
        break
      case 'date':
        result.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
        break
      case 'article_count':
        result.sort((a, b) => b.article_count - a.article_count)
        break
    }

    return result
  })

  // 监听天数变化，自动刷新
  watch(days, () => {
    fetchClusters()
  })

  return {
    clusters,
    loading,
    days,
    sortBy,
    onlyEmerging,
    filteredClusters,
    fetchClusters,
  }
}
