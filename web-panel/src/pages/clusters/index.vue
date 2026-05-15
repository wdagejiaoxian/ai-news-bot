<template>
  <div class="clusters-page">
    <!-- 页面标题 -->
    <div class="page-header">
      <h2>主题聚类</h2>
      <p class="page-desc">基于向量相似度的文章主题聚类与热点发现</p>
    </div>

    <!-- 筛选条件 -->
    <div class="filter-bar">
      <el-select v-model="days" placeholder="时间范围" style="width: 120px">
        <el-option label="最近7天" :value="7" />
        <el-option label="最近14天" :value="14" />
        <el-option label="最近30天" :value="30" />
        <el-option label="最近90天" :value="90" />
      </el-select>

      <el-select v-model="sortBy" placeholder="排序方式" style="width: 120px">
        <el-option label="按热度" value="hotness" />
        <el-option label="按日期" value="date" />
        <el-option label="按文章数" value="article_count" />
      </el-select>

      <el-checkbox v-model="onlyEmerging">仅显示新兴话题</el-checkbox>
    </div>

    <!-- 趋势图表 -->
    <ClusterChart :clusters="filteredClusters" :days="days" />

    <!-- 聚类列表 -->
    <div class="cluster-list" v-loading="loading">
      <el-empty v-if="!loading && filteredClusters.length === 0" description="暂无聚类数据" />

      <div
        v-for="cluster in filteredClusters"
        :key="cluster.id"
        class="cluster-card"
        :class="{ 'cluster-card--emerging': cluster.is_emerging }"
        @click="handleClusterClick(cluster)"
      >
        <div class="cluster-header">
          <div class="cluster-keywords">
            <el-tag
              v-for="keyword in cluster.keywords.slice(0, 5)"
              :key="keyword"
              size="small"
              :type="cluster.is_emerging ? 'warning' : ''"
            >
              {{ keyword }}
            </el-tag>
          </div>
          <div class="cluster-badges">
            <el-tag v-if="cluster.is_emerging" type="warning" size="small" effect="dark">
              新兴
            </el-tag>
          </div>
        </div>

        <div class="cluster-meta">
          <span class="meta-item">
            <el-icon><Document /></el-icon>
            {{ cluster.article_count }} 篇文章
          </span>
          <span class="meta-item">
            <el-icon><Star /></el-icon>
            平均评分 {{ cluster.avg_score.toFixed(1) }}
          </span>
          <span class="meta-item">
            <el-icon><TrendCharts /></el-icon>
            热度 {{ cluster.hotness.toFixed(2) }}
          </span>
          <span class="meta-item">
            <el-icon><Calendar /></el-icon>
            {{ formatDate(cluster.date) }}
          </span>
        </div>
      </div>
    </div>

    <!-- 聚类详情抽屉 -->
    <el-drawer
      v-model="drawerVisible"
      :title="drawerTitle"
      :size="isMobile ? '100%' : '50%'"
      direction="rtl"
    >
      <ClusterDetail :cluster-id="selectedClusterId" />
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Document, Star, TrendCharts, Calendar } from '@element-plus/icons-vue'
import { useClusters } from './composables/useClusters'
import ClusterDetail from './components/ClusterDetail.vue'
import ClusterChart from './components/ClusterChart.vue'
import type { ClusterTopic } from '@/types/vector'

const {
  loading,
  days,
  sortBy,
  onlyEmerging,
  filteredClusters,
  fetchClusters,
} = useClusters()

const drawerVisible = ref(false)
const selectedClusterId = ref<number | null>(null)
const isMobile = ref(false)

const checkMobile = () => {
  isMobile.value = window.innerWidth <= 768
}

const drawerTitle = computed(() => {
  // 可以根据选中的聚类显示标题
  return '聚类详情'
})

const formatDate = (dateStr: string) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleDateString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
  })
}

const handleClusterClick = (cluster: ClusterTopic) => {
  selectedClusterId.value = cluster.id
  drawerVisible.value = true
}

onMounted(() => {
  fetchClusters()
  checkMobile()
  window.addEventListener('resize', checkMobile)
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
})
</script>

<style scoped>
.clusters-page {
  padding: 20px;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0 0 8px 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.page-header .page-desc {
  margin: 0;
  color: var(--color-text-muted);
  font-size: 14px;
}

.filter-bar {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.cluster-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.cluster-card {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.2s;
}

.cluster-card:hover {
  border-color: var(--color-primary);
  box-shadow: var(--shadow-md);
}

.cluster-card--emerging {
  border-left: 3px solid var(--color-warning);
}

.cluster-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}

.cluster-keywords {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.cluster-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  color: var(--color-text-secondary);
  font-size: 13px;
}

.cluster-meta .meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

@media (max-width: 768px) {
  .clusters-page {
    padding: 12px;
  }

  .filter-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .filter-bar .el-select {
    width: 100% !important;
  }

  .cluster-meta {
    flex-direction: column;
    gap: 8px;
  }
}
</style>
