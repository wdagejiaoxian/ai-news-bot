<template>
  <div class="articles-page">
    <!-- 筛选栏 -->
    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" :model="filters" class="filter-form">
        <el-form-item label="来源">
          <el-select
            v-model="filters.source"
            clearable
            placeholder="全部来源"
            style="width: 160px;"
            filterable
            @change="handleFilterChange"
          >
            <el-option
              v-for="source in rssSources"
              :key="source.id"
              :label="source.name"
              :value="source.name"
            />
          </el-select>
        </el-form-item>
        
        <el-form-item label="状态">
          <el-select v-model="filters.status" clearable placeholder="全部状态" style="width: 120px;" @change="handleFilterChange">
            <el-option label="待处理" value="pending" />
            <el-option label="已处理" value="processed" />
            <el-option label="已发布" value="published" />
            <el-option label="已归档" value="archived" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="评分">
          <el-input-number
            v-model="filters.minScore"
            :min="0"
            :max="100"
            :step="1"
            placeholder="最低分"
            controls-position="right"
            style="width: 120px;"
          />
          <span class="score-separator">-</span>
          <el-input-number
            v-model="filters.maxScore"
            :min="0"
            :max="100"
            :step="1"
            placeholder="最高分"
            controls-position="right"
            style="width: 120px;"
          />
        </el-form-item>
        
        <el-form-item label="关键词">
          <el-input
            v-model="filters.keyword"
            :placeholder="searchMode === 'semantic' ? '语义搜索...' : '搜索标题、摘要'"
            clearable
            style="width: 200px;"
            @keyup.enter="handleSearch"
          />
        </el-form-item>

        <el-form-item>
          <el-tooltip
            :content="unavailableReason || '启用语义搜索'"
            placement="top"
          >
            <el-switch
              v-model="searchMode"
              active-value="semantic"
              inactive-value="keyword"
              active-text="语义"
              inactive-text="关键词"
              :disabled="!semanticSearchAvailable"
              @change="handleSearchModeChange"
            />
          </el-tooltip>
        </el-form-item>

        <!-- T10: 排序权重滑块（仅语义搜索时显示） -->
        <el-form-item v-if="searchMode === 'semantic'" label="排序">
          <el-tooltip
            content="调整相似度与评分的排序权重"
            placement="top"
          >
            <div class="weight-slider">
              <span class="weight-label">相似度</span>
              <el-slider
                v-model="sortWeights.similarity"
                :min="0"
                :max="1"
                :step="0.1"
                :show-tooltip="true"
                :format-tooltip="(val: number) => `相似度: ${(val * 100).toFixed(0)}% / 评分: ${((1 - val) * 100).toFixed(0)}%`"
                style="width: 120px;"
                @change="handleWeightChange"
              />
              <span class="weight-label">评分</span>
            </div>
          </el-tooltip>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="handleSearch">
            <el-icon><Search /></el-icon>
            搜索
          </el-button>
          <el-button @click="handleReset">
            <el-icon><Refresh /></el-icon>
            重置
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
    
    <!-- 数据表格 -->
    <el-card shadow="never">
      <el-table
        v-loading="loading"
        :data="articles"
        style="width: 100%"
        @sort-change="handleSortChange"
      >
        <el-table-column prop="title" label="标题" min-width="180">
          <template #default="{ row }">
            <span class="article-title" @click="$router.push(`/articles/${row.id}`)">
              {{ row.title }}
            </span>
          </template>
        </el-table-column>

        <el-table-column prop="source_name" label="来源" width="130" align="center">
          <template #default="{ row }">
            <span class="cell-text">{{ row.source_name || '-' }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="score" label="评分" width="100" align="center" sortable="custom">
          <template #default="{ row }">
            <span class="cell-text">{{ row.score?.toFixed(1) || '-' }}</span>
          </template>
        </el-table-column>

        <!-- T7: 相似度列（仅语义搜索时显示） -->
        <el-table-column
          v-if="searchMode === 'semantic'"
          prop="similarity"
          label="相似度"
          width="100"
          align="center"
          sortable="custom"
        >
          <template #default="{ row }">
            <el-tag
              size="small"
              :type="getSimilarityTagType(row.similarity)"
            >
              {{ row.similarity != null ? (row.similarity * 100).toFixed(0) + '%' : '-' }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="getStatusType(row.status)">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="created_at" label="采集时间" width="160" align="center" sortable="custom">
          <template #default="{ row }">
            <span class="cell-text">{{ formatDate(row.created_at) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="180" fixed="right" align="center">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button type="primary" link @click="$router.push(`/articles/${row.id}`)">
                查看
              </el-button>
              <el-button type="default" link @click="handleArchive(row)">
                归档
              </el-button>
              <el-popconfirm
                title="确定删除这篇文章吗？"
                @confirm="handleDelete(row)"
              >
                <template #reference>
                  <el-button type="danger" link>删除</el-button>
                </template>
              </el-popconfirm>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <!-- 空状态 -->
      <div v-if="!loading && articles.length === 0" class="empty-state">
        <div class="empty-state__icon">
          <el-icon :size="32"><Document /></el-icon>
        </div>
        <div class="empty-state__title">暂无文章</div>
        <div class="empty-state__desc">在 RSS 源页面添加订阅后，文章将自动显示在这里</div>
      </div>

      <!-- 分页 -->
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="semanticSearchTotal"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handlePageChange"
        />

        <!-- T12: 语义搜索提示 -->
        <div v-if="searchMode === 'semantic'" class="semantic-hint">
          <el-text type="info" size="small">
            语义搜索最多显示 {{ MAX_SEMANTIC_PAGES }} 页结果
          </el-text>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { useDebounceFn } from '@vueuse/core'
import { request } from '@/api'
import { getEmbeddingHealth, getVectorDBHealth } from '@/api/vector'
import { semanticSearchCache } from '@/utils/semanticSearchCache'
import dayjs from 'dayjs'

interface Article {
  id: number
  title: string
  source: string
  source_name: string
  score: number | null
  status: string
  created_at: string
  similarity?: number | null
}

interface RSSSource {
  id: number
  name: string
  url: string
  category: string | null
  is_active: boolean
}

const loading = ref(false)
const articles = ref<Article[]>([])
const rssSources = ref<RSSSource[]>([])

const filters = reactive({
  source: '',
  status: '',
  minScore: undefined as number | undefined,
  maxScore: undefined as number | undefined,
  keyword: '',
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0,
})

const sortParams = reactive({
  sortBy: 'created_at',
  sortOrder: 'desc',
})

// T11: localStorage key for search mode persistence
const SEARCH_MODE_KEY = 'articles_search_mode'

// T12: 语义搜索最大页数限制
const MAX_SEMANTIC_PAGES = 5

// T11: Initialize searchMode from localStorage (with validation)
const savedMode = localStorage.getItem(SEARCH_MODE_KEY)
const searchMode = ref<'keyword' | 'semantic'>(
  (savedMode === 'semantic' || savedMode === 'keyword') ? savedMode : 'keyword'
)

const semanticSearchAvailable = ref(false)
const unavailableReason = ref('')

// T10: 排序权重状态（相似度权重, 评分权重）
const sortWeights = reactive({
  similarity: 0.7,
  score: 0.3,
})

// T12: 计算语义搜索的有效总数（限制最多 5 页）
const semanticSearchTotal = computed(() => {
  if (searchMode.value === 'semantic') {
    const maxResults = MAX_SEMANTIC_PAGES * pagination.pageSize
    return Math.min(pagination.total, maxResults)
  }
  return pagination.total
})

async function checkSemanticSearchAvailability() {
  try {
    const [embeddingRes, dbRes] = await Promise.all([
      getEmbeddingHealth(),
      getVectorDBHealth(),
    ])

    // 注意：axios 拦截器已经解包响应，embeddingRes 和 dbRes 直接是 data 对象
    const embeddingOk = embeddingRes.available ?? false
    const dbOk = dbRes.available ?? false
    const dimensionOk = (embeddingRes.models_compatibility?.compatible_count ?? 0) > 0

    semanticSearchAvailable.value = embeddingOk && dbOk && dimensionOk

    if (!embeddingOk) unavailableReason.value = 'Embedding 模型未配置或不可用'
    else if (!dbOk) unavailableReason.value = '向量数据库未连接'
    else if (!dimensionOk) unavailableReason.value = 'Embedding 模型维度与当前配置不兼容'
    else unavailableReason.value = ''
  } catch {
    semanticSearchAvailable.value = false
    unavailableReason.value = '无法获取向量服务状态'
  }
}

function getScoreType(score: number | null) {
  if (!score) return 'info'
  if (score >= 85) return 'success'
  if (score >= 65) return 'warning'
  return 'danger'
}

/**
 * T7: 获取相似度标签颜色
 * - ≥ 80%: success (绿色)
 * - ≥ 60%: warning (橙色)
 * - < 60%: danger (红色)
 * - null/undefined: info (灰色)
 */
function getSimilarityTagType(similarity: number | null | undefined): string {
  if (similarity == null) return 'info'
  if (similarity >= 0.8) return 'success'
  if (similarity >= 0.6) return 'warning'
  return 'danger'
}

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

function formatDate(date: string) {
  return date ? dayjs(date).format('YYYY-MM-DD HH:mm') : '-'
}

async function fetchArticles() {
  loading.value = true
  try {
    // T12: 语义搜索时检查前端缓存
    if (searchMode.value === 'semantic' && filters.keyword) {
      const cached = semanticSearchCache.get(
        filters.keyword,
        { source: filters.source, status: filters.status, minScore: filters.minScore, maxScore: filters.maxScore },
        sortWeights
      )

      if (cached) {
        // 从缓存分页（client-side 分页）
        const startIdx = (pagination.page - 1) * pagination.pageSize
        articles.value = cached.results.slice(startIdx, startIdx + pagination.pageSize)
        pagination.total = cached.total

        console.debug('[SemanticSearch] 前端缓存命中，条数:', cached.results.length)
        loading.value = false
        return
      }
    }

    // 缓存未命中，请求后端
    const params: any = {
      // 语义搜索始终请求第一页（用于获取完整数据给前端缓存）
      // 关键词搜索使用当前页码
      page: searchMode.value === 'semantic' ? 1 : pagination.page,
      page_size: searchMode.value === 'semantic' ? 100 : pagination.pageSize,
      sort_by: sortParams.sortBy,
      sort_order: sortParams.sortOrder,
      search_mode: searchMode.value,
    }

    if (filters.source) params.source = filters.source
    if (filters.status) params.status = filters.status
    if (filters.minScore !== undefined) params.min_score = filters.minScore
    if (filters.maxScore !== undefined) params.max_score = filters.maxScore
    if (filters.keyword) params.keyword = filters.keyword

    // T10: 语义搜索时传递排序权重参数
    if (searchMode.value === 'semantic') {
      params.sort_weight_similarity = sortWeights.similarity
      params.sort_weight_score = sortWeights.score
    }

    const data = await request.get('/articles/', { params })

    // T12: 语义搜索时缓存完整结果
    if (searchMode.value === 'semantic' && filters.keyword && data.items) {
      semanticSearchCache.set(
        filters.keyword,
        { source: filters.source, status: filters.status, minScore: filters.minScore, maxScore: filters.maxScore },
        sortWeights,
        data.items,
        data.total || 0
      )
      console.debug('[SemanticSearch] 后端数据已缓存，条数:', data.items.length)
    }

    // 更新分页数据
    pagination.total = data.total || 0

    // T12: 前端分页（从缓存或刚请求的数据）
    if (searchMode.value === 'semantic') {
      const startIdx = (pagination.page - 1) * pagination.pageSize
      articles.value = (data.items || []).slice(startIdx, startIdx + pagination.pageSize)
    } else {
      // 关键词搜索：使用后端分页
      articles.value = data.items || []
    }

    // T9: 语义搜索无结果时提示
    if (searchMode.value === 'semantic' && articles.value.length === 0 && filters.keyword) {
      ElMessage.info({
        message: '未找到语义相关文章，建议切换为关键词搜索',
        duration: 5000,
        showClose: true,
      })
    }
  } catch (error: any) {
    // T8: 语义搜索不可用时自动降级（优化提示体验）
    if (searchMode.value === 'semantic' && error?.response?.status === 400) {
      ElMessage.warning({
        message: '语义搜索不可用，已切换为关键词搜索',
        duration: 5000,
        showClose: true,
      })
      // T11: 降级时清除 localStorage 记忆，下次默认关键词搜索
      searchMode.value = 'keyword'
      localStorage.setItem(SEARCH_MODE_KEY, 'keyword')
      checkSemanticSearchAvailability()
      fetchArticles()
      return
    }
    console.error('获取文章列表失败:', error)
    ElMessage.error('获取文章列表失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

// 评分筛选器 debounce（800ms）
const debouncedFetch = useDebounceFn(() => {
  pagination.page = 1
  fetchArticles()
}, 800)

// 仅监听评分范围变化（其他筛选条件通过 handleFilterChange 或 handleSearch 触发）
watch(
  () => [filters.minScore, filters.maxScore],
  () => {
    debouncedFetch()
  }
)

function handleFilterChange() {
  // 来源、状态下拉框变化时立即触发搜索
  pagination.page = 1
  fetchArticles()
}

function handleSearch() {
  pagination.page = 1
  fetchArticles()
}

function handleReset() {
  filters.source = ''
  filters.status = ''
  filters.minScore = undefined
  filters.maxScore = undefined
  filters.keyword = ''
  pagination.page = 1
  fetchArticles()
}

function handleSearchModeChange() {
  // T11: 切换搜索模式时保存到 localStorage
  localStorage.setItem(SEARCH_MODE_KEY, searchMode.value)
  pagination.page = 1
  fetchArticles()
}

/**
 * T10: 权重变化处理
 * 权重变化时自动搜索
 */
function handleWeightChange() {
  pagination.page = 1
  fetchArticles()
}

function handleSortChange({ prop, order }: { prop: string; order: string }) {
  sortParams.sortBy = prop || 'created_at'
  sortParams.sortOrder = order === 'ascending' ? 'asc' : 'desc'
  fetchArticles()
}

function handleSizeChange(size: number) {
  pagination.pageSize = size
  pagination.page = 1
  fetchArticles()
}

function handlePageChange(page: number) {
  // T12: 语义搜索翻页限制
  if (searchMode.value === 'semantic') {
    const maxPage = Math.ceil(pagination.total / pagination.pageSize)
    const effectiveMaxPage = Math.min(maxPage, MAX_SEMANTIC_PAGES)

    if (page > effectiveMaxPage) {
      ElMessage.warning({
        message: `语义搜索最多显示 ${MAX_SEMANTIC_PAGES} 页结果，建议优化搜索词或切换为关键词搜索`,
        duration: 3000,
      })
      return
    }
  }

  pagination.page = page

  // T12: 语义搜索模式从缓存读取（无需请求后端）
  if (searchMode.value === 'semantic' && filters.keyword) {
    const cached = semanticSearchCache.get(
      filters.keyword,
      { source: filters.source, status: filters.status, minScore: filters.minScore, maxScore: filters.maxScore },
      sortWeights
    )

    if (cached) {
      const startIdx = (page - 1) * pagination.pageSize
      articles.value = cached.results.slice(startIdx, startIdx + pagination.pageSize)
      console.debug('[SemanticSearch] 翻页（缓存）:', page, '条数:', cached.results.length)
      return
    }
  }

  fetchArticles()
}

async function handleArchive(row: Article) {
  try {
    await request.put(`/articles/${row.id}`, { status: 'archived' })
    ElMessage.success('已归档')
    fetchArticles()
  } catch (error) {
    ElMessage.error('归档失败')
  }
}

async function handleDelete(row: Article) {
  try {
    await request.delete(`/articles/${row.id}`)
    ElMessage.success('已删除')
    fetchArticles()
  } catch (error) {
    ElMessage.error('删除失败')
  }
}

async function fetchSources() {
  try {
    const data = await request.get('/rss-sources/')
    rssSources.value = data.items || []
  } catch (error) {
    console.error('获取RSS源列表失败:', error)
  }
}

onMounted(() => {
  fetchArticles()
  fetchSources()
  checkSemanticSearchAvailability()
})
</script>

<style scoped>
.articles-page {
  padding: 0;
}

.filter-card {
  margin-bottom: var(--spacing-lg);
}

.filter-form {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-sm);
}

.score-separator {
  margin: 0 var(--spacing-sm);
  color: var(--color-text-muted);
}

/* 表格标题样式 */
.article-title {
  display: block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--color-primary);
  cursor: pointer;
  transition: color var(--transition-duration-fast) var(--transition-timing);
}

.article-title:hover {
  color: var(--color-primary-hover);
  text-decoration: underline;
}

/* 单元格文本 - 可换行 */
.cell-text {
  display: block;
  width: 100%;
  text-align: center;
  word-break: break-word;
  white-space: normal;
  line-height: 1.5;
}

/* 操作按钮容器 */
.action-buttons {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: var(--spacing-xs);
  flex-wrap: nowrap;
  min-width: max-content;
}

.pagination-wrapper {
  margin-top: var(--spacing-lg);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

/* T12: 语义搜索提示样式 */
.semantic-hint {
  text-align: center;
}

/* T10: 权重滑块样式 */
.weight-slider {
  display: flex;
  align-items: center;
  gap: 8px;
}

.weight-label {
  font-size: 12px;
  color: #909399;
  white-space: nowrap;
}
</style>
