<template>
  <div class="rsshub-help-page">
    <!-- 区块 1: 服务状态卡片 -->
    <el-card shadow="never" class="status-card">
      <template #header>
        <div class="card-header">
          <span>📡 RSSHub 服务状态</span>
          <div class="status-actions">
            <el-tooltip content="更新镜像并重启容器，不会同步路由，更新后请手动同步路由" placement="top">
              <el-button
                type="warning"
                size="small"
                :loading="updating"
                @click="handleUpdate"
              >
                更新 RSSHub
              </el-button>
            </el-tooltip>
            <el-tooltip content="从容器提取最新路由文件并同步到数据库" placement="top">
              <el-button
                type="primary"
                size="small"
                :loading="syncing"
                :disabled="rsshubStatus?.status !== 'running'"
                @click="handleSyncRoutes"
              >
                同步路由
              </el-button>
            </el-tooltip>
            <el-tooltip content="启动 RSSHub 容器，不会同步路由" placement="top">
              <el-button
                v-if="rsshubStatus?.status !== 'running'"
                type="primary"
                size="small"
                :loading="starting"
                @click="handleStart"
              >
                启动服务
              </el-button>
            </el-tooltip>
            <el-button
              v-if="rsshubStatus?.status === 'running'"
              type="danger"
              size="small"
              :loading="stopping"
              @click="handleStop"
            >
              停止服务
            </el-button>
            <el-button size="small" @click="fetchStatus">
              刷新状态
            </el-button>
          </div>
        </div>
      </template>

      <div v-if="rsshubStatus" class="status-content">
        <div class="status-info">
          <el-tag :type="statusTagType" size="large">
            {{ statusLabel }}
          </el-tag>
          <span class="status-detail">
            <template v-if="rsshubStatus.status === 'running'">
              运行中 · {{ rsshubStatus.routes_count || 0 }} 条路由 · 来源: {{ rsshubStatus.routes_source === 'live' ? '实时' : '内置副本' }}
            </template>
            <template v-else-if="rsshubStatus.status === 'starting'">
              启动中...
            </template>
            <template v-else>
              未运行
              <span v-if="rsshubStatus.message" class="status-message">：{{ rsshubStatus.message }}</span>
            </template>
          </span>
        </div>
        <div v-if="rsshubStatus.version" class="version-info">
          版本: {{ rsshubStatus.version }}
        </div>
      </div>
      <el-skeleton v-else :rows="2" animated />
    </el-card>

    <!-- 区块 2: 什么是 RSSHub -->
    <el-card shadow="never" class="intro-card">
      <template #header>💡 什么是 RSSHub</template>
      <div class="intro-content">
        <p>
          RSSHub 是一个开源的 RSS 源生成器，它可以帮您将任何一个网站转化为 RSS 订阅源。
          有了 RSSHub，您就可以用 RSS 阅读器订阅几乎任何网站的内容。
        </p>
        <p>
          <strong>主要优势：</strong>
        </p>
        <ul>
          <li>支持 10,000+ 公开路由，覆盖社交媒体、新闻、博客等多个领域</li>
          <li>自托管部署，完全可控，数据不经过第三方</li>
          <li>开源免费，社区活跃，持续更新</li>
        </ul>
        <div class="intro-links">
          <el-link href="https://github.com/DIYgod/RSSHub" target="_blank" type="primary">
            <el-icon><Link /></el-icon>
            GitHub 仓库
          </el-link>
          <el-link href="https://docs.rsshub.app" target="_blank" type="primary">
            <el-icon><Link /></el-icon>
            官方文档
          </el-link>
          <el-link href="https://docs.rsshub.app/routes" target="_blank" type="primary">
            <el-icon><Link /></el-icon>
            支持的路由
          </el-link>
        </div>
      </div>
    </el-card>

    <!-- 区块 3: 快速部署指引 -->
    <el-card shadow="never" class="deploy-card">
      <template #header>🚀 快速部署指引</template>

      <el-alert
        v-if="!dockerAvailable"
        title="Docker 未安装"
        type="warning"
        :closable="false"
        show-icon
        class="docker-warning"
      >
        <template #default>
          检测到当前环境未安装 Docker。请先安装 Docker 以使用 RSSHub 功能。
          <div class="docker-install-links">
            <el-link href="https://docs.docker.com/desktop/install/windows-install/" target="_blank" type="primary">
              Windows 安装指南
            </el-link>
            <el-link href="https://docs.docker.com/desktop/install/mac-install/" target="_blank" type="primary">
              Mac 安装指南
            </el-link>
            <el-link href="https://docs.docker.com/engine/install/" target="_blank" type="primary">
              Linux 安装指南
            </el-link>
          </div>
        </template>
      </el-alert>

      <div v-else class="deploy-content">
        <div class="deploy-step">
          <div class="step-number">1</div>
          <div class="step-content">
            <h4>启动 RSSHub 容器</h4>
            <p>在项目根目录执行以下命令启动 RSSHub：</p>
            <pre class="code-block"><code>{{ startCommand }}</code></pre>
          </div>
        </div>

        <div class="deploy-step">
          <div class="step-number">2</div>
          <div class="step-content">
            <h4>验证服务状态</h4>
            <p>启动后返回本页面查看服务状态，等待状态变为「运行中」即可使用。</p>
          </div>
        </div>

        <div class="deploy-note">
          <el-icon><InfoFilled /></el-icon>
          <span>RSSHub 容器会在后台持续运行。重启机器后需要重新启动服务。</span>
        </div>
      </div>
    </el-card>

    <!-- 区块 4: 浏览器插件推荐 -->
    <el-card shadow="never" class="plugin-card">
      <template #header>🔧 浏览器插件推荐</template>
      <div class="plugin-content">
        <p>
          推荐安装 <strong>RSSHub Radar</strong> 浏览器插件，可以一键发现网页的 RSS 订阅源，
          并自动生成 RSSHub 路由地址。
        </p>

        <div class="plugin-links">
          <el-link href="https://chrome.google.com/webstore/detail/rsshub-radar/fakdajnbpklfhpibfjlnhgmbkhbmaced" target="_blank" type="primary">
            <el-icon><Link /></el-icon>
            Chrome / Edge
          </el-link>
          <el-link href="https://addons.mozilla.org/firefox/addon/rsshub-radar/" target="_blank" type="primary">
            <el-icon><Link /></el-icon>
            Firefox
          </el-link>
        </div>

        <el-divider />

        <h4>URL 转换示例</h4>
        <p>使用 RSSHub 后，您可以轻松转换网页链接为 RSS 订阅地址：</p>

        <div class="url-example">
          <div class="example-item">
            <span class="example-label">原链接：</span>
            <el-link href="https://twitter.com/user_name" target="_blank">
              https://twitter.com/user_name
            </el-link>
          </div>
          <div class="example-arrow">↓</div>
          <div class="example-item">
            <span class="example-label">RSSHub：</span>
            <pre class="code-block"><code>{{ rsshubUrl }}/twitter/user/user_name</code></pre>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 区块 5: 路由列表 -->
    <el-card shadow="never" class="routes-card">
      <template #header>
        <div class="routes-header">
          <span>🌐 支持的路由列表</span>
          <span v-if="routesSource" class="routes-source">
            来源: {{ routesSource === 'live' ? '实时数据' : '内置副本' }}
            <el-tooltip v-if="routesSource === 'bundled'" content="当前路由数据来自内置副本，建议启动 RSSHub 服务以获取最新路由">
              <el-icon><Warning /></el-icon>
            </el-tooltip>
          </span>
        </div>
      </template>

      <!-- 筛选器 -->
      <div class="routes-filters">
        <el-select
          v-model="filterLang"
          placeholder="语言"
          clearable
          style="width: 120px"
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
          style="width: 150px"
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
          style="width: 200px"
          @input="debounceSearch"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
      </div>

      <!-- 路由表格 -->
      <el-table
        v-loading="routesLoading"
        :data="routes"
        stripe
        style="width: 100%"
        class="routes-table"
      >
        <el-table-column prop="route_path" label="路由路径" min-width="200">
          <template #default="{ row }">
            <el-link :href="buildRouteUrl(row)" target="_blank" type="primary">
              {{ row.route_path }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column prop="route_name" label="名称" width="150">
          <template #default="{ row }">
            {{ row.route_name || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="namespace_id" label="命名空间" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.namespace_id" size="small" type="warning">{{ row.namespace_id }}</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="domain" label="域名" width="150" />
        <el-table-column prop="category" label="分类" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.category" size="small">{{ row.category }}</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="lang" label="语言" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.lang" size="small" type="info">{{ row.lang }}</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="copyRouteUrl(row)">
              复制链接
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="routes-pagination">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="totalRoutes"
          layout="prev, pager, next, total"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Link, InfoFilled, Warning, Search } from '@element-plus/icons-vue'
import { request } from '@/api'

// ==================== 类型定义 ====================

interface RSSHubStatus {
  status: 'running' | 'stopped' | 'starting' | 'unknown' | 'docker_unavailable' | 'error'
  docker_available: boolean
  rsshub_url: string
  version?: string
  routes_count?: number
  routes_source?: 'live' | 'bundled'
  checked_at?: string
  auto_start_enabled?: boolean
  message?: string
  last_error?: string | null
}

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

interface OperationResponse {
  success: boolean
  message: string
}

interface RouteSyncResponse {
  success: boolean
  message: string
  inserted: number
  updated: number
  deleted: number
}

// ==================== 状态 ====================

const rsshubStatus = ref<RSSHubStatus | null>(null)
const starting = ref(false)
const stopping = ref(false)
const updating = ref(false)
const syncing = ref(false)
const routesLoading = ref(false)
const routes = ref<RouteItem[]>([])
const routesSource = ref<'live' | 'bundled' | null>(null)
const currentPage = ref(1)
const pageSize = ref(20)
const totalRoutes = ref(0)
const availableLanguages = ref<string[]>([])
const availableCategories = ref<string[]>([])
const filterLang = ref('')
const filterCategory = ref('')
const filterKeyword = ref('')

let statusPollingTimer: number | null = null
let searchDebounceTimer: number | null = null

// ==================== 计算属性 ====================

const dockerAvailable = computed(() => rsshubStatus.value?.docker_available ?? false)

const rsshubUrl = computed(() => rsshubStatus.value?.rsshub_url || 'http://localhost:1200')

const statusLabel = computed(() => {
  switch (rsshubStatus.value?.status) {
    case 'running': return '运行中'
    case 'starting': return '启动中'
    case 'docker_unavailable':
      return rsshubStatus.value?.message || 'Docker 环境不可用'
    case 'stopped': return '未运行'
    case 'error': return '启动失败'
    default: return '未知'
  }
})

const statusTagType = computed(() => {
  switch (rsshubStatus.value?.status) {
    case 'running': return 'success'
    case 'starting': return 'info'
    case 'stopped': return 'danger'
    default: return 'warning'
  }
})

const startCommand = computed(() =>
  'docker-compose -f docker-compose.rsshub.yml up -d'
)

// ==================== 方法 ====================

async function fetchStatus() {
  try {
    const data = await request.get<RSSHubStatus>('/rsshub/status')
    rsshubStatus.value = data
  } catch {
    // 静默处理，服务未运行时 API 可能报错
    rsshubStatus.value = {
      status: 'stopped',
      docker_available: false,
      rsshub_url: 'http://localhost:1200',
    }
  }
}

async function handleStart() {
  starting.value = true
  try {
    const data = await request.post<OperationResponse>('/rsshub/start')
    if (data.success) {
      ElMessage.success('RSSHub 启动命令已发送，请等待服务启动...')
      startPolling()
    } else {
      ElMessage.error(data.message || '启动失败')
    }
  } catch (e: any) {
    ElMessage.error(e.message || '启动失败')
  } finally {
    starting.value = false
  }
}

async function handleStop() {
  stopping.value = true
  try {
    const data = await request.post<OperationResponse>('/rsshub/stop')
    if (data.success) {
      ElMessage.success('RSSHub 已停止')
      await fetchStatus()
    } else {
      ElMessage.error(data.message || '停止失败')
    }
  } catch (e: any) {
    ElMessage.error(e.message || '停止失败')
  } finally {
    stopping.value = false
  }
}

async function handleUpdate() {
  updating.value = true
  try {
    const data = await request.post<OperationResponse>('/rsshub/update')
    if (data.success) {
      ElMessage.success('RSSHub 镜像更新并重启成功')
      await fetchStatus()
    } else {
      ElMessage.error(data.message || '更新失败')
    }
  } catch (e: any) {
    ElMessage.error(e.message || '更新失败')
  } finally {
    updating.value = false
  }
}

async function handleSyncRoutes() {
  syncing.value = true
  try {
    const data = await request.post<RouteSyncResponse>('/rsshub/sync-routes')
    if (data.success) {
      ElMessage.success(
        `路由同步完成：新增 ${data.inserted} 条，更新 ${data.updated} 条，删除 ${data.deleted} 条`
      )
      await fetchStatus()
      fetchRoutes()
    } else {
      ElMessage.error(data.message || '同步失败')
    }
  } catch (e: any) {
    ElMessage.error(e.message || '同步失败')
  } finally {
    syncing.value = false
  }
}

async function fetchRoutes() {
  routesLoading.value = true
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
    routesSource.value = data.source
    totalRoutes.value = data.total
    availableLanguages.value = data.available_filters.languages
    availableCategories.value = data.available_filters.categories
  } catch (e: any) {
    ElMessage.error(e.message || '获取路由列表失败')
  } finally {
    routesLoading.value = false
  }
}

function handleFilterChange() {
  currentPage.value = 1
  fetchRoutes()
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
  fetchRoutes()
}

function buildRouteUrl(route: RouteItem): string {
  return `${rsshubUrl.value}${route.route_path}`
}

async function copyRouteUrl(route: RouteItem) {
  const url = buildRouteUrl(route)
  try {
    await navigator.clipboard.writeText(url)
    ElMessage.success('链接已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败，请手动复制')
  }
}

function startPolling() {
  // 停止之前的轮询
  if (statusPollingTimer !== null) {
    clearInterval(statusPollingTimer)
  }
  // 立即获取一次状态
  fetchStatus()
  // 每 30 秒轮询一次
  statusPollingTimer = window.setInterval(() => {
    fetchStatus()
    // 如果服务已运行，停止轮询
    if (rsshubStatus.value?.status === 'running') {
      if (statusPollingTimer !== null) {
        clearInterval(statusPollingTimer)
        statusPollingTimer = null
      }
      // 同时刷新路由列表
      fetchRoutes()
    }
  }, 30000)
}

onMounted(() => {
  fetchStatus()
  fetchRoutes()
  startPolling()
})

onUnmounted(() => {
  if (statusPollingTimer !== null) {
    clearInterval(statusPollingTimer)
    statusPollingTimer = null
  }
  if (searchDebounceTimer !== null) {
    clearTimeout(searchDebounceTimer)
    searchDebounceTimer = null
  }
})
</script>

<style scoped>
.rsshub-help-page {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
  max-width: 1200px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.status-actions {
  display: flex;
  gap: var(--spacing-sm);
}

.status-content {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.status-info {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.status-detail {
  color: var(--color-text-secondary);
  font-size: var(--font-size-small);
}

.status-message {
  color: var(--color-text-muted);
}

.version-info {
  font-size: var(--font-size-small);
  color: var(--color-text-muted);
}

.intro-content p {
  margin-bottom: var(--spacing-sm);
  line-height: 1.6;
  color: var(--color-text-secondary);
}

.intro-content ul {
  margin-bottom: var(--spacing-md);
  padding-left: var(--spacing-lg);
  color: var(--color-text-secondary);
}

.intro-content li {
  margin-bottom: var(--spacing-xs);
}

.intro-links {
  display: flex;
  gap: var(--spacing-lg);
  margin-top: var(--spacing-md);
}

.docker-warning {
  margin-bottom: var(--spacing-sm);
}

.docker-install-links {
  display: flex;
  gap: var(--spacing-md);
  margin-top: var(--spacing-sm);
}

.deploy-content {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

.deploy-step {
  display: flex;
  gap: var(--spacing-md);
}

.step-number {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--color-primary);
  color: var(--color-text-inverse);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: var(--font-weight-semibold);
  flex-shrink: 0;
}

.step-content h4 {
  margin: 0 0 var(--spacing-xs);
  font-size: var(--font-size-body);
  color: var(--color-text-primary);
}

.step-content p {
  margin: 0;
  font-size: var(--font-size-small);
  color: var(--color-text-secondary);
}

.deploy-note {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--color-primary-alpha-05);
  border-radius: var(--radius-md);
  font-size: var(--font-size-small);
  color: var(--color-text-secondary);
}

.plugin-content p {
  margin-bottom: var(--spacing-sm);
  line-height: 1.6;
  color: var(--color-text-secondary);
}

.plugin-links {
  display: flex;
  gap: var(--spacing-lg);
  margin: var(--spacing-md) 0;
}

.url-example {
  background: var(--color-bg-content);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
  margin-top: var(--spacing-sm);
}

.example-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.example-label {
  font-weight: var(--font-weight-medium);
  color: var(--color-text-secondary);
  min-width: 60px;
}

.example-arrow {
  text-align: center;
  color: var(--color-text-muted);
  padding: var(--spacing-xs) 0;
}

.routes-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.routes-source {
  font-size: var(--font-size-small);
  color: var(--color-text-muted);
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
}

.routes-filters {
  display: flex;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-md);
  flex-wrap: wrap;
}

.routes-table {
  margin-top: var(--spacing-sm);
}

.routes-pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: var(--spacing-md);
}

.code-block {
  background: var(--color-bg-content);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--spacing-sm) var(--spacing-md);
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: var(--font-size-small);
  color: var(--color-text-primary);
  overflow-x: auto;
  margin: var(--spacing-xs) 0;
}

.code-block code {
  white-space: pre;
}
</style>
