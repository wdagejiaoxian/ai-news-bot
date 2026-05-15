<template>
  <div class="github-page">
    <!-- 采集语言配置卡片 -->
    <el-card shadow="never" class="languages-card">
      <template #header>
        <div class="languages-header">
          <span>采集语言配置</span>
          <el-button size="small" @click="showLanguageDialog">
            <el-icon><Plus /></el-icon>
            添加语言
          </el-button>
        </div>
      </template>
      <div class="languages-content">
        <div v-if="allLanguages.length === 0" class="languages-empty">
          暂未配置采集语言，将使用默认语言：Python、JavaScript、TypeScript、Go
        </div>
        <div v-else class="languages-tags">
          <el-tag
            v-for="lang in allLanguages"
            :key="lang.id"
            class="language-tag"
            :type="lang.is_active ? 'success' : 'info'"
            :closable="true"
            @close="handleDeleteLanguage(lang)"
            @click="handleToggleLanguage(lang)"
          >
            <span v-if="lang.color" class="lang-color" :style="{ backgroundColor: lang.color }"></span>
            {{ lang.name }}
            <span class="lang-status">{{ lang.is_active ? '' : '(已停用)' }}</span>
          </el-tag>
        </div>
      </div>
    </el-card>

    <!-- 筛选栏 -->
    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" :model="filters" class="filter-form">
        <el-form-item label="语言">
          <el-select v-model="filters.language" clearable placeholder="全部语言" style="width: 120px;">
            <el-option
              v-for="lang in languages"
              :key="lang"
              :label="lang"
              :value="lang"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="最低Stars">
          <el-input-number
            v-model="filters.minStars"
            :min="0"
            placeholder="最低Stars"
            controls-position="right"
            style="width: 150px;"
          />
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
        :data="repos"
        style="width: 100%"
        @sort-change="handleSortChange"
      >
        <el-table-column prop="full_name" label="项目" min-width="250">
          <template #default="{ row }">
            <el-link :href="row.url" target="_blank" type="primary">
              {{ row.full_name }}
            </el-link>
            <div class="repo-desc" v-if="row.description">
              {{ row.description }}
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="language" label="语言" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.language" size="small">{{ row.language }}</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>

        <el-table-column prop="stars" label="Stars" width="120" sortable="custom">
          <template #default="{ row }">
            <span class="stars">⭐ {{ formatNumber(row.stars) }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="forks" label="Forks" width="100">
          <template #default="{ row }">
            <span class="forks">🍴 {{ formatNumber(row.forks) }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="stars_today" label="今日Stars" width="120">
          <template #default="{ row }">
            <span class="today-stars" v-if="row.stars_today > 0">
              +{{ row.stars_today }}
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>

        <el-table-column prop="score" label="评分" width="100" sortable="custom">
          <template #default="{ row }">
            <el-tag :type="getScoreType(row.score)">
              {{ row.score?.toFixed(1) || '-' }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="trending_date" label="采集日期" width="120">
          <template #default="{ row }">
            {{ formatDate(row.trending_date) }}
          </template>
        </el-table-column>
      </el-table>

      <!-- 空状态 -->
      <div v-if="!loading && repos.length === 0" class="empty-state">
        <div class="empty-state__icon">
          <el-icon :size="32"><Github /></el-icon>
        </div>
        <div class="empty-state__title">暂无 GitHub 热门项目</div>
        <div class="empty-state__desc">GitHub Trending 每天 22:00 自动采集，请稍后再来看看</div>
      </div>

      <!-- 分页 -->
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <!-- 添加语言对话框 -->
    <el-dialog v-model="languageDialogVisible" title="添加采集语言" width="400px">
      <el-form :model="languageForm" label-width="100px">
        <el-form-item label="语言名称">
          <el-input v-model="languageForm.name" placeholder="如 Python、JavaScript" />
        </el-form-item>
        <el-form-item label="颜色代码">
          <div class="color-input-wrapper">
            <el-color-picker v-model="languageForm.color" show-alpha />
            <el-input
              v-model="languageForm.color"
              placeholder="如 #3572A5"
              class="color-input"
            />
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="languageDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="languageSubmitting" @click="handleAddLanguage">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useDebounceFn } from '@vueuse/core'
import { request } from '@/api'
import dayjs from 'dayjs'

interface GitHubRepo {
  id: number
  full_name: string
  description: string | null
  url: string
  language: string | null
  stars: number
  forks: number
  stars_today: number
  score: number | null
  trending_date: string
}

interface GitHubLanguage {
  id: number
  name: string
  color: string | null
  is_active: boolean
}

const DEFAULT_LANGUAGES = ['Python', 'JavaScript', 'TypeScript', 'Go']

const loading = ref(false)
const repos = ref<GitHubRepo[]>([])
const languages = ref<string[]>([])
const allLanguages = ref<GitHubLanguage[]>([])
const languageDialogVisible = ref(false)
const languageSubmitting = ref(false)

const languageForm = reactive({
  name: '',
  color: '',
})

async function fetchLanguages() {
  try {
    const data = await request.get('/github-languages/')
    allLanguages.value = data.items || []
    // 只获取已启用的语言用于筛选
    const activeLanguages = allLanguages.value.filter((item: GitHubLanguage) => item.is_active)
    if (activeLanguages.length > 0) {
      languages.value = activeLanguages.map((item: GitHubLanguage) => item.name)
    } else {
      languages.value = DEFAULT_LANGUAGES
    }
  } catch (error) {
    console.error('获取语言列表失败:', error)
    ElMessage.error('获取语言列表失败')
    languages.value = DEFAULT_LANGUAGES
  }
}

async function fetchRepos() {
  loading.value = true
  try {
    const params: any = {
      page: pagination.page,
      page_size: pagination.pageSize,
      sort_by: sortParams.sortBy,
      sort_order: sortParams.sortOrder,
    }

    if (filters.language) params.language = filters.language
    if (filters.minStars !== undefined) params.min_stars = filters.minStars

    const data = await request.get('/github-repos/', { params })
    repos.value = data.items || []
    pagination.total = data.total || 0
  } catch (error) {
    console.error('获取GitHub项目列表失败:', error)
    ElMessage.error('获取GitHub项目列表失败')
  } finally {
    loading.value = false
  }
}

function showLanguageDialog() {
  languageForm.name = ''
  languageForm.color = ''
  languageDialogVisible.value = true
}

async function handleAddLanguage() {
  if (!languageForm.name) {
    ElMessage.warning('请输入语言名称')
    return
  }
  languageSubmitting.value = true
  try {
    const payload: any = { name: languageForm.name, is_active: true }
    if (languageForm.color) {
      payload.color = languageForm.color
    }
    await request.post('/github-languages/', payload)
    ElMessage.success('添加成功')
    languageDialogVisible.value = false
    fetchLanguages()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '添加失败')
  } finally {
    languageSubmitting.value = false
  }
}

async function handleToggleLanguage(lang: GitHubLanguage) {
  try {
    await request.put(`/github-languages/${lang.id}`, {
      is_active: !lang.is_active
    })
    ElMessage.success(lang.is_active ? '已停用' : '已启用')
    fetchLanguages()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

async function handleDeleteLanguage(lang: GitHubLanguage) {
  try {
    await request.delete(`/github-languages/${lang.id}`)
    ElMessage.success('删除成功')
    fetchLanguages()
  } catch (error) {
    ElMessage.error('删除失败')
  }
}

const filters = reactive({
  language: '',
  minStars: undefined as number | undefined,
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0,
})

const sortParams = reactive({
  sortBy: 'stars',
  sortOrder: 'desc',
})

function getScoreType(score: number | null) {
  if (!score) return 'info'
  if (score >= 8) return 'success'
  if (score >= 6) return 'warning'
  return 'danger'
}

function formatNumber(num: number) {
  if (num >= 1000000) {
    return (num / 1000000).toFixed(1) + 'M'
  }
  if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'k'
  }
  return num.toString()
}

function formatDate(date: string) {
  return date ? dayjs(date).format('YYYY-MM-DD') : '-'
}

// 筛选器 debounce（300ms）
const debouncedFetch = useDebounceFn(() => {
  pagination.page = 1
  fetchRepos()
}, 300)

watch(
  () => [filters.language, filters.minStars],
  () => {
    debouncedFetch()
  }
)

function handleSearch() {
  pagination.page = 1
  fetchRepos()
}

function handleReset() {
  filters.language = ''
  filters.minStars = undefined
  pagination.page = 1
  fetchRepos()
}

function handleSortChange({ prop, order }: { prop: string; order: string }) {
  sortParams.sortBy = prop || 'stars'
  sortParams.sortOrder = order === 'ascending' ? 'asc' : 'desc'
  fetchRepos()
}

function handleSizeChange(size: number) {
  pagination.pageSize = size
  pagination.page = 1
  fetchRepos()
}

function handlePageChange(page: number) {
  pagination.page = page
  fetchRepos()
}

onMounted(() => {
  fetchRepos()
  fetchLanguages()
})
</script>

<style scoped>
.github-page {
  padding: 0;
}

.languages-card {
  margin-bottom: var(--spacing-lg);
}

.languages-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.languages-content {
  min-height: 40px;
}

.languages-empty {
  color: var(--el-text-color-secondary);
  font-size: 14px;
}

.languages-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-sm);
}

.language-tag {
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
}

.lang-color {
  width: 12px;
  height: 12px;
  border-radius: 3px;
  flex-shrink: 0;
}

.lang-status {
  font-size: 12px;
  opacity: 0.7;
}

.color-preview {
  display: inline-block;
  width: 20px;
  height: 20px;
  border-radius: 4px;
  vertical-align: middle;
}

.color-input-wrapper {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.color-input-wrapper .el-color-picker {
  flex-shrink: 0;
}

.color-input-wrapper .color-input {
  flex: 1;
}

.filter-card {
  margin-bottom: var(--spacing-lg);
}

.filter-form {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-sm);
}

.repo-desc {
  font-size: var(--font-size-small);
  color: var(--color-text-muted);
  margin-top: var(--spacing-xs);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 400px;
}

.stars {
  color: var(--color-warning);
  font-weight: var(--font-weight-semibold);
}

.forks {
  color: var(--color-text-muted);
}

.today-stars {
  color: var(--color-success);
  font-weight: var(--font-weight-semibold);
}

.pagination-wrapper {
  margin-top: var(--spacing-lg);
  display: flex;
  justify-content: flex-end;
}
</style>
