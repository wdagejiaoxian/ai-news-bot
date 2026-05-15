<template>
  <div class="article-detail" v-loading="loading">
    <el-card shadow="never" class="detail-card">
      <template #header>
        <div class="card-header">
          <el-button @click="$router.back()">
            <el-icon><ArrowLeft /></el-icon>
            返回
          </el-button>
          <div class="actions">
            <el-button type="default" @click="handleArchive">
              归档
            </el-button>
            <el-button type="primary" @click="handleReprocess">
              重新处理
            </el-button>
          </div>
        </div>
      </template>
      
      <div class="article-content" v-if="article">
        <h1 class="article-title">{{ article.title }}</h1>
        
        <div class="article-meta">
          <el-tag :type="getStatusType(article.status)">
            {{ getStatusText(article.status) }}
          </el-tag>
          <span class="meta-item">
            <el-icon><Connection /></el-icon>
            {{ article.source }}
          </span>
          <span class="meta-item" v-if="article.source_name">
            <el-icon><Link /></el-icon>
            {{ article.source_name }}
          </span>
          <span class="meta-item">
            <el-icon><Clock /></el-icon>
            {{ formatDate(article.created_at) }}
          </span>
          <el-tag :type="getScoreType(article.score)" class="score-tag">
            评分: {{ article.score?.toFixed(1) || '-' }}
          </el-tag>
        </div>
        
        <el-divider />
        
        <div class="article-section" v-if="article.summary">
          <h3>摘要</h3>
          <div
            class="summary"
            :class="{ 'is-html': isHtmlContent(article.summary) }"
            v-html="formatContent(article.summary)"
          />
        </div>

        <div class="article-section" v-if="article.content">
          <h3>文章内容</h3>
          <div
            class="content-body"
            :class="{ 'is-html': isHtmlContent(article.content) }"
            v-html="formatContent(article.content)"
          />
        </div>
        
        <div class="article-section" v-if="article.tags">
          <h3>标签</h3>
          <div class="tags">
            <el-tag
              v-for="tag in article.tags.split(',')"
              :key="tag"
              size="small"
              class="tag"
            >
              {{ tag.trim() }}
            </el-tag>
          </div>
        </div>
        
        <div class="article-section" v-if="article.keywords">
          <h3>关键词</h3>
          <div class="keywords">
            <el-tag
              v-for="keyword in article.keywords.split(',')"
              :key="keyword"
              type="info"
              size="small"
              class="keyword"
            >
              {{ keyword.trim() }}
            </el-tag>
          </div>
        </div>
        
        <el-divider />
        
        <div class="article-link">
          <el-link :href="article.url" target="_blank" type="primary">
            <el-icon><Link /></el-icon>
            查看原文
          </el-link>
        </div>

        <!-- 相似文章推荐 -->
        <div class="similar-section" v-if="similarArticles.length > 0">
          <el-divider />
          <h3>相似文章推荐</h3>
          <div class="similar-list">
            <div
              v-for="item in similarArticles"
              :key="item.article_id"
              class="similar-item"
              @click="goToArticle(item.article_id)"
            >
              <div class="similar-title">{{ item.title }}</div>
              <div class="similar-meta">
                <el-tag size="small" type="info">
                  相似度: {{ (item.similarity * 100).toFixed(0) }}%
                </el-tag>
                <el-tag
                  v-if="item.score"
                  size="small"
                  :type="getScoreType(item.score)"
                >
                  评分: {{ item.score.toFixed(1) }}
                </el-tag>
              </div>
            </div>
          </div>
        </div>

        <!-- 无相似文章提示 -->
        <div v-else-if="!similarLoading && article" class="no-similar">
          <el-divider />
          <el-empty description="暂无相似文章" :image-size="60" />
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { request } from '@/api'
import { getSimilarArticles } from '@/api/vector'
import type { SearchResult } from '@/types/vector'
import dayjs from 'dayjs'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const article = ref<any>(null)
const similarArticles = ref<SearchResult[]>([])
const similarLoading = ref(false)

function getStatusType(status: string) {
  const map: Record<string, string> = {
    pending: 'info',
    processed: 'success',
    published: 'primary',
    archived: 'warning',
  }
  return map[status] || 'info'
}

function getStatusText(status: string) {
  const map: Record<string, string> = {
    pending: '待处理',
    processed: '已处理',
    published: '已发布',
    archived: '已归档',
  }
  return map[status] || status
}

function getScoreType(score: number | null) {
  if (!score) return 'info'
  if (score >= 85) return 'success'
  if (score >= 65) return 'warning'
  return 'danger'
}

function formatDate(date: string) {
  return date ? dayjs(date).format('YYYY-MM-DD HH:mm') : '-'
}

// 检测内容是否包含HTML标签
function isHtmlContent(content: string): boolean {
  if (!content) return false
  return /<[a-z][\s\S]*>/i.test(content)
}

// 格式化内容：如果是纯文本，转换为段落；如果是HTML，直接返回
function formatContent(content: string): string {
  if (!content) return ''
  if (isHtmlContent(content)) {
    // 清理HTML内容，保留结构但确保安全
    return content
      .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '') // 移除script标签
      .replace(/on\w+="[^"]*"/gi, '') // 移除事件属性
      .replace(/on\w+='[^']*'/gi, '') // 移除事件属性
  }
  // 纯文本：按换行符分段，每段放入<p>标签
  return content
    .split(/\n\n+/)
    .map(p => p.trim())
    .filter(p => p)
    .map(p => `<p>${p.replace(/\n/g, '<br>')}</p>`)
    .join('')
}

async function fetchArticle() {
  loading.value = true
  try {
    const data = await request.get(`/articles/${route.params.id}`)
    article.value = data
  } catch (error) {
    ElMessage.error('获取文章详情失败')
    router.back()
  } finally {
    loading.value = false
  }
}

async function handleArchive() {
  try {
    await request.put(`/articles/${article.value.id}`, { status: 'archived' })
    ElMessage.success('已归档')
    fetchArticle()
  } catch (error) {
    ElMessage.error('归档失败')
  }
}

async function handleReprocess() {
  try {
    await request.post(`/articles/${article.value.id}/reprocess`)
    ElMessage.success('已标记为待处理')
    fetchArticle()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

onMounted(() => {
  fetchArticle()
  fetchSimilarArticles()
})

/**
 * 获取相似文章推荐
 */
async function fetchSimilarArticles() {
  if (!route.params.id) return

  similarLoading.value = true
  try {
    const data = await getSimilarArticles(Number(route.params.id), 5)
    similarArticles.value = data || []
  } catch (error) {
    console.warn('获取相似文章失败:', error)
    similarArticles.value = []
  } finally {
    similarLoading.value = false
  }
}

/**
 * 跳转到相似文章详情页
 */
function goToArticle(articleId: number) {
  router.push(`/articles/${articleId}`)
}
</script>

<style scoped>
.article-detail {
  padding: 0;
  max-width: 1200px;
  margin: 0 auto;
}

.detail-card {
  border-radius: var(--radius-xl);
  width: 100%;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.article-title {
  font-size: var(--font-size-h3);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  margin: 0 0 var(--spacing-md);
  line-height: 1.4;
}

.article-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--spacing-md);
  color: var(--color-text-muted);
  font-size: var(--font-size-small);
}

.meta-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
}

.score-tag {
  margin-left: auto;
}

.article-section {
  margin-bottom: var(--spacing-lg);
}

.article-section h3 {
  font-size: var(--font-size-body);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  margin: 0 0 var(--spacing-sm);
}

.summary {
  color: var(--color-text-secondary);
  line-height: 1.8;
  margin: 0;
}

/* HTML内容样式 */
.content-body.is-html,
.summary.is-html {
  color: var(--color-text-secondary);
  line-height: 1.8;
}

.content-body.is-html p,
.summary.is-html p {
  margin: 0 0 1em 0;
}

.content-body.is-html p:last-child,
.summary.is-html p:last-child {
  margin-bottom: 0;
}

.content-body.is-html h1,
.content-body.is-html h2,
.content-body.is-html h3,
.content-body.is-html h4,
.content-body.is-html h5,
.content-body.is-html h6,
.summary.is-html h1,
.summary.is-html h2,
.summary.is-html h3,
.summary.is-html h4,
.summary.is-html h5,
.summary.is-html h6 {
  color: var(--color-text-primary);
  font-weight: var(--font-weight-semibold);
  margin: 1.2em 0 0.6em 0;
  line-height: 1.4;
}

.content-body.is-html h1,
.summary.is-html h1 {
  font-size: var(--font-size-h2);
}

.content-body.is-html h2,
.summary.is-html h2 {
  font-size: var(--font-size-h3);
}

.content-body.is-html h3,
.summary.is-html h3 {
  font-size: var(--font-size-h4);
}

.content-body.is-html h4,
.summary.is-html h4 {
  font-size: var(--font-size-body);
}

.content-body.is-html h5,
.summary.is-html h5,
.content-body.is-html h6,
.summary.is-html h6 {
  font-size: var(--font-size-small);
}

.content-body.is-html strong,
.content-body.is-html b,
.summary.is-html strong,
.summary.is-html b {
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}

.content-body.is-html a,
.summary.is-html a {
  color: var(--color-primary);
  text-decoration: none;
}

.content-body.is-html a:hover,
.summary.is-html a:hover {
  text-decoration: underline;
}

.content-body.is-html ul,
.content-body.is-html ol,
.summary.is-html ul,
.summary.is-html ol {
  margin: 0.5em 0;
  padding-left: 1.5em;
}

.content-body.is-html li,
.summary.is-html li {
  margin: 0.3em 0;
}

.content-body.is-html blockquote,
.summary.is-html blockquote {
  margin: 1em 0;
  padding: 0.5em 1em;
  border-left: 3px solid var(--color-primary);
  background: var(--color-bg-content);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  color: var(--color-text-secondary);
}

.content-body.is-html code,
.summary.is-html code {
  font-family: var(--font-family-mono);
  background: var(--color-bg-content);
  padding: 0.15em 0.4em;
  border-radius: var(--radius-sm);
  font-size: 0.9em;
}

.content-body.is-html pre,
.summary.is-html pre {
  background: var(--color-bg-content);
  padding: 1em;
  border-radius: var(--radius-md);
  overflow-x: auto;
  margin: 1em 0;
}

.content-body.is-html pre code,
.summary.is-html pre code {
  background: none;
  padding: 0;
}

.tags,
.keywords {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-sm);
}

.article-link {
  margin-top: var(--spacing-lg);
}

.similar-section {
  margin-top: var(--spacing-lg);
}

.similar-section h3 {
  font-size: var(--font-size-body);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  margin: var(--spacing-md) 0 var(--spacing-sm);
}

.similar-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.similar-item {
  padding: var(--spacing-sm) var(--spacing-md);
  border-radius: var(--radius-sm);
  background: var(--color-bg-content);
  cursor: pointer;
  transition: all 0.2s ease;
}

.similar-item:hover {
  background: var(--color-bg-hover);
  transform: translateX(4px);
}

.similar-title {
  font-size: var(--font-size-body);
  color: var(--color-text-primary);
  margin-bottom: var(--spacing-xs);
  line-height: 1.4;
}

.similar-meta {
  display: flex;
  gap: var(--spacing-xs);
  flex-wrap: wrap;
}

.no-similar {
  margin-top: var(--spacing-lg);
  padding: var(--spacing-md) 0;
}
</style>
