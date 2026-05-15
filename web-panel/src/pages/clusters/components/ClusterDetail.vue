<template>
  <div class="cluster-detail" v-loading="loading">
    <el-empty v-if="!loading && !cluster" description="暂无数据" />

    <template v-if="cluster">
      <!-- 聚类信息 -->
      <div class="cluster-info">
        <div class="info-header">
          <div class="keywords">
            <el-tag
              v-for="keyword in cluster.keywords"
              :key="keyword"
              :type="cluster.is_emerging ? 'warning' : ''"
            >
              {{ keyword }}
            </el-tag>
          </div>
          <el-tag v-if="cluster.is_emerging" type="warning" effect="dark">新兴话题</el-tag>
        </div>

        <div class="info-stats">
          <div class="stat-item">
            <span class="stat-label">文章数</span>
            <span class="stat-value">{{ cluster.article_count }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">平均评分</span>
            <span class="stat-value">{{ cluster.avg_score.toFixed(1) }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">热度</span>
            <span class="stat-value">{{ cluster.hotness.toFixed(2) }}</span>
          </div>
        </div>
      </div>

      <!-- 文章列表 -->
      <div class="articles-section">
        <h4>包含的文章</h4>
        <div class="article-list">
          <div
            v-for="article in articles"
            :key="article.id"
            class="article-item"
            @click="goToArticle(article.id)"
          >
            <div class="article-title">{{ article.title }}</div>
            <div class="article-meta">
              <el-tag v-if="article.score" size="small" type="success">
                {{ article.score }}分
              </el-tag>
              <span v-if="article.source_name" class="source">{{ article.source_name }}</span>
            </div>
          </div>
          <el-empty v-if="articles.length === 0" description="暂无文章数据" :image-size="60" />
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { getClusterDetail } from '@/api/vector'
import type { ClusterTopic, ClusterArticle } from '@/types/vector'

const props = defineProps<{
  clusterId: number | null
}>()

const router = useRouter()
const loading = ref(false)
const cluster = ref<ClusterTopic | null>(null)
const articles = ref<ClusterArticle[]>([])

const fetchDetail = async (id: number) => {
  loading.value = true
  try {
    const data = await getClusterDetail(id)
    if (data) {
      cluster.value = data.cluster
      articles.value = data.articles || []
    }
  } catch (error) {
    console.error('获取聚类详情失败:', error)
    cluster.value = null
    articles.value = []
  } finally {
    loading.value = false
  }
}

const goToArticle = (articleId: number) => {
  router.push(`/articles/${articleId}`)
}

watch(
  () => props.clusterId,
  (newId) => {
    if (newId) {
      fetchDetail(newId)
    } else {
      cluster.value = null
      articles.value = []
    }
  },
  { immediate: true }
)
</script>

<style scoped>
.cluster-detail {
  padding: 16px;
}

.cluster-info {
  margin-bottom: 24px;
}

.info-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}

.keywords {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.info-stats {
  display: flex;
  gap: 24px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.stat-label {
  font-size: 12px;
  color: var(--color-text-muted);
  margin-bottom: 4px;
}

.stat-value {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.articles-section h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.article-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.article-item {
  padding: 12px;
  background: var(--color-bg-content);
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.2s;
}

.article-item:hover {
  background: var(--color-primary-alpha-10);
}

.article-title {
  font-size: 14px;
  color: var(--color-text-primary);
  margin-bottom: 8px;
  line-height: 1.4;
}

.article-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--color-text-muted);
}

@media (max-width: 768px) {
  .info-stats {
    flex-direction: column;
    gap: 12px;
  }

  .article-title {
    font-size: 13px;
  }
}
</style>
