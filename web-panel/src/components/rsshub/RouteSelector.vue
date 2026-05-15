<template>
  <div class="route-selector">
    <el-collapse v-model="collapsed">
      <el-collapse-item title="从路由模板选择（或直接输入 URL）" name="selector">
        <!-- 筛选器 -->
        <div class="selector-filters">
          <el-select
            v-model="filterLang"
            placeholder="语言"
            clearable
            size="small"
            style="width: 100px"
            @change="handleFilterChange"
          >
            <el-option label="全部语言" value="" />
            <el-option
              v-for="lang in availableLanguages"
              :key="lang"
              :label="lang"
              :value="lang"
            />
          </el-select>

          <el-select
            v-model="filterCategory"
            placeholder="分类"
            clearable
            size="small"
            style="width: 130px"
            @change="handleFilterChange"
          >
            <el-option label="全部分类" value="" />
            <el-option
              v-for="cat in availableCategories"
              :key="cat"
              :label="cat"
              :value="cat"
            />
          </el-select>

          <el-input
            v-model="filterKeyword"
            placeholder="搜索路由..."
            clearable
            size="small"
            style="width: 180px"
            @input="debounceSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </div>

        <!-- 路由列表 -->
        <div v-loading="loading" class="route-list">
          <div v-if="routes.length === 0 && !loading" class="empty-state">
            <el-empty description="未找到匹配的路由" :image-size="60" />
          </div>

          <div
            v-for="route in routes"
            :key="`${route.namespace_id}:${route.route_path}`"
            class="route-item"
            :class="{ 'route-item--selected': selectedRoute?.namespace_id === route.namespace_id && selectedRoute?.route_path === route.route_path }"
            @click="selectRoute(route)"
          >
            <div class="route-item__radio">
              <el-radio
                :model-value="selectedRoute?.namespace_id === route.namespace_id && selectedRoute?.route_path === route.route_path"
                size="small"
              />
            </div>
            <div class="route-item__content">
              <div class="route-item__path">
                <code>{{ route.route_path }}</code>
              </div>
              <div class="route-item__meta">
                <span v-if="route.route_name" class="route-item__name">{{ route.route_name }}</span>
                <el-tag v-if="route.category" size="small" type="info">{{ route.category }}</el-tag>
                <span class="route-item__domain">{{ route.domain }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 分页 -->
        <div v-if="totalRoutes > pageSize" class="selector-pagination">
          <el-pagination
            v-model:current-page="currentPage"
            :page-size="pageSize"
            :total="totalRoutes"
            layout="prev, pager, next"
            :pager-count="5"
            size="small"
            @current-change="handlePageChange"
          />
        </div>

        <!-- 选中路由提示 -->
        <div v-if="selectedRoute?.has_params" class="params-hint">
          <el-icon><InfoFilled /></el-icon>
          <span>该路由包含参数，请将 URL 中的 <code>{参数}</code> 替换为实际值</span>
        </div>
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, InfoFilled } from '@element-plus/icons-vue'
import { request } from '@/api'

// ==================== Props / Emits ====================

interface Props {
  modelValue: string
  rsshubBaseUrl: string
}

interface Emits {
  (e: 'update:modelValue', v: string): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// ==================== 类型定义 ====================

interface RouteItem {
  route_path: string
  route_name?: string
  namespace_id?: string
  domain: string
  example_path?: string
  category?: string
  categories: string
  lang: string
  has_params: boolean
  description?: string
  maintainers: string
  features: string
  source_file: string
}

interface FiltersMeta {
  languages: string[]
  categories: string[]
}

interface RSSHubRoutesResponse {
  routes: RouteItem[]
  total: number
  page: number
  page_size: number
  source: 'live' | 'bundled'
  updated_at: string
  available_filters: FiltersMeta
}

// ==================== 状态 ====================

const collapsed = ref(['selector'])
const loading = ref(false)
const routes = ref<RouteItem[]>([])
const selectedRoute = ref<RouteItem | null>(null)
const currentPage = ref(1)
const pageSize = ref(10)
const totalRoutes = ref(0)
const availableLanguages = ref<string[]>([])
const availableCategories = ref<string[]>([])
const filterLang = ref('')
const filterCategory = ref('')
const filterKeyword = ref('')

let searchDebounceTimer: number | null = null
let filtersInitialized = false

// ==================== 方法 ====================

async function initFilters() {
  if (filtersInitialized) return

  try {
    const data = await request.get<RSSHubRoutesResponse>('/rsshub/routes', {
      params: { page: 1, page_size: 1 }
    })
    availableLanguages.value = data.available_filters.languages
    availableCategories.value = data.available_filters.categories
    filtersInitialized = true
  } catch (e: any) {
    console.error('获取路由过滤器失败:', e.message)
  }
}

async function loadRoutes() {
  loading.value = true
  try {
    const params: Record<string, any> = {
      page: currentPage.value,
      page_size: pageSize.value,
    }
    if (filterLang.value) params.lang = filterLang.value
    if (filterCategory.value) params.category = filterCategory.value
    if (filterKeyword.value) params.keyword = filterKeyword.value

    const data = await request.get<RSSHubRoutesResponse>('/rsshub/routes', { params })
    routes.value = data.routes
    totalRoutes.value = data.total

    if (!filtersInitialized) {
      availableLanguages.value = data.available_filters.languages
      availableCategories.value = data.available_filters.categories
      filtersInitialized = true
    }
  } catch (e: any) {
    ElMessage.error(e.message || '获取路由列表失败')
  } finally {
    loading.value = false
  }
}

function handleFilterChange() {
  currentPage.value = 1
  loadRoutes()
}

function debounceSearch() {
  if (searchDebounceTimer !== null) {
    clearTimeout(searchDebounceTimer)
  }
  searchDebounceTimer = window.setTimeout(() => {
    handleFilterChange()
  }, 300)
}

function handlePageChange() {
  loadRoutes()
}

function selectRoute(route: RouteItem) {
  selectedRoute.value = route
  const url = `${props.rsshubBaseUrl}${route.route_path}`
  emit('update:modelValue', url)

  if (route.has_params) {
    ElMessage({ message: '请将 URL 中的 {参数} 替换为实际值', duration: 4000, type: 'info' })
  } else {
    ElMessage.success('URL 已填入')
  }
}

// 初始化：尝试从已有 modelValue 匹配选中路由
function syncSelectedFromModelValue() {
  if (!props.modelValue || routes.value.length === 0) return

  const matched = routes.value.find(r =>
    props.modelValue === `${props.rsshubBaseUrl}${r.route_path}`
  )
  if (matched) {
    selectedRoute.value = matched
  }
}

// ==================== 监听 ====================

watch([filterLang, filterCategory], () => {
  if (filtersInitialized) {
    handleFilterChange()
  }
})

watch(() => props.modelValue, () => {
  syncSelectedFromModelValue()
})

// ==================== 生命周期 ====================

onMounted(async () => {
  await initFilters()
  await loadRoutes()
  syncSelectedFromModelValue()
})
</script>

<style scoped>
.route-selector {
  margin-top: var(--spacing-sm);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-content);
}

:deep(.el-collapse) {
  border: none;
}

:deep(.el-collapse-item__header) {
  padding: var(--spacing-sm) var(--spacing-md);
  font-size: var(--font-size-small);
  color: var(--color-text-secondary);
  background: transparent;
  border-bottom: 1px solid var(--color-border);
}

:deep(.el-collapse-item__wrap) {
  border: none;
  background: transparent;
}

:deep(.el-collapse-item__content) {
  padding: var(--spacing-sm);
}

.selector-filters {
  display: flex;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-sm);
  flex-wrap: wrap;
}

.route-list {
  max-height: 300px;
  overflow-y: auto;
}

.route-list::-webkit-scrollbar {
  width: 4px;
}

.route-list::-webkit-scrollbar-thumb {
  background: var(--color-primary-alpha-30);
  border-radius: 2px;
}

.empty-state {
  padding: var(--spacing-md);
  text-align: center;
}

.route-item {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background-color var(--transition-duration-fast);
}

.route-item:hover {
  background: var(--color-white-alpha-08);
}

.route-item--selected {
  background: var(--color-primary-alpha-10);
}

.route-item__radio {
  padding-top: 2px;
  flex-shrink: 0;
}

.route-item__content {
  flex: 1;
  min-width: 0;
}

.route-item__path {
  font-size: var(--font-size-small);
  margin-bottom: var(--spacing-xs);
}

.route-item__path code {
  color: var(--color-text-primary);
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: var(--font-size-small);
}

.route-item__meta {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  flex-wrap: wrap;
}

.route-item__name {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.route-item__domain {
  font-size: 12px;
  color: var(--color-text-muted);
}

.selector-pagination {
  display: flex;
  justify-content: center;
  margin-top: var(--spacing-sm);
  padding-top: var(--spacing-sm);
  border-top: 1px solid var(--color-border);
}

.params-hint {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  margin-top: var(--spacing-sm);
  padding: var(--spacing-sm);
  background: var(--color-primary-alpha-05);
  border-radius: var(--radius-md);
  font-size: var(--font-size-small);
  color: var(--color-text-secondary);
}

.params-hint code {
  color: var(--color-primary);
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  padding: 0 2px;
}
</style>