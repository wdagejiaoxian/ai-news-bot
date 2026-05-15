<template>
  <div class="rss-page">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>我的RSS源</span>
          <el-button type="primary" @click="showDialog">
            <el-icon><Plus /></el-icon>
            添加RSS源
          </el-button>
        </div>
      </template>

      <!-- T-21: RSSHub 状态卡片 -->
      <el-alert
        v-if="rsshubStatus"
        :type="rsshubAlertType"
        :closable="false"
        show-icon
        class="rsshub-status-alert"
      >
        <template #title>
          <div class="status-bar">
            <span>📡 RSSHub：<el-tag :type="rsshubTagType" size="small">{{ rsshubStatusLabel }}</el-tag></span>
            <span v-if="rsshubStatus.status !== 'running'" class="status-help-link">
              <router-link to="/rsshub-help">查看帮助 →</router-link>
            </span>
          </div>
          <div v-if="rsshubStatus.message && rsshubStatus.status !== 'running'" class="rsshub-status-desc">
            {{ rsshubStatus.message }}
          </div>
        </template>
      </el-alert>

      <!-- 无活跃源警告 -->
      <el-alert
        v-if="showWarning"
        title="暂无活跃的RSS源"
        type="warning"
        :closable="false"
        show-icon
        class="no-active-source-alert"
      >
        <template #default>
          <p>系统无法采集新闻，请添加RSS源或启用现有源。</p>
          <el-button type="primary" size="small" @click="showDialog">
            添加RSS源
          </el-button>
        </template>
      </el-alert>

      <el-alert
        v-if="sources.length === 0"
        title="您还没有配置任何RSS源，请添加后开始使用。"
        type="info"
        :closable="false"
        class="empty-alert"
      />
      
      <el-table v-loading="loading" :data="sources" style="width: 100%">
        <el-table-column prop="name" label="名称" width="200" />
        <el-table-column prop="url" label="URL" min-width="300">
          <template #default="{ row }">
            <el-link :href="row.url" target="_blank" type="primary">{{ row.url }}</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="category" label="分类" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.category" size="small">{{ row.category }}</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="source_type" label="源类型" width="150">
          <template #default="{ row }">
            <el-tooltip
              v-if="row.source_type === 'rsshub' && !isRSSHubRunning"
              content="RSSHub 服务未运行，此源可能无法正常采集"
              placement="top"
            >
              <el-tag type="danger" size="small" class="rsshub-warning-tag">
                ⚠ {{ sourceTypeLabel(row.source_type) }}
              </el-tag>
            </el-tooltip>
            <el-tag
              v-else
              :type="sourceTypeTagType(row.source_type)"
              size="small"
            >
              {{ sourceTypeLabel(row.source_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
              {{ row.is_active ? '已启用' : '已停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="fetch_error_count" label="解析错误" width="100">
          <template #default="{ row }">
            <span :class="{ 'text-danger': row.fetch_error_count > 0 }">
              {{ row.fetch_error_count }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="article_count" label="文章数" width="100" />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button
              type="primary"
              link
              :disabled="row.source_type === 'rsshub' && row.rsshub_unavailable && !row.is_active"
              @click="handleToggleActive(row)"
            >
              {{ row.is_active ? '停用' : '启用' }}
            </el-button>
            <el-tooltip
              v-if="row.source_type === 'rsshub' && row.rsshub_unavailable && !row.is_active"
              content="RSSHub 服务未运行，请先启动"
              placement="top"
            >
              <el-tag type="warning" size="small" style="margin-left: 4px;">不可启用</el-tag>
            </el-tooltip>
            <el-popconfirm title="确定删除这个RSS源配置吗？" @confirm="handleDelete(row)">
              <template #reference>
                <el-button type="danger" link>删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <!-- 空状态 -->
      <div v-if="!loading && sources.length === 0" class="empty-state">
        <div class="empty-state__icon">
          <el-icon :size="32"><Connection /></el-icon>
        </div>
        <div class="empty-state__title">暂无 RSS 源</div>
        <div class="empty-state__desc">点击上方"添加RSS源"开始订阅您喜欢的内容</div>
      </div>
    </el-card>
    
    <!-- 添加对话框 -->
    <el-dialog v-model="dialogVisible" title="添加RSS源" width="500px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px" @keyup.enter="handleSubmit">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入名称" />
        </el-form-item>
        <el-form-item label="URL" prop="url">
          <el-input
            v-model="form.url"
            :placeholder="urlPlaceholder"
          >
            <template #append>
              <el-button :loading="validating" @click="handleValidate">校验</el-button>
            </template>
          </el-input>
          <div v-if="form.source_type === 'auto'" class="url-hint">
            系统将自动检测此网站的RSS订阅地址
          </div>
          <RouteSelector
            v-if="form.source_type === 'rsshub' && isRSSHubRunning"
            v-model="form.url"
            :rsshub-base-url="rsshubBaseUrl"
            class="route-selector-wrapper"
          />
        </el-form-item>
        <el-form-item label="分类">
          <el-input v-model="form.category" placeholder="请输入分类（可选）" />
        </el-form-item>
        <el-form-item label="源类型">
          <div class="source-type-wrapper">
            <el-select v-model="form.source_type" placeholder="请选择源类型" style="width: 100%">
              <el-option label="标准 RSS" value="standard" />
              <el-option label="RSSHub 生成" value="rsshub" :disabled="!isRSSHubRunning">
                <template v-if="!isRSSHubRunning">
                  <el-tooltip content="RSSHub 服务未运行，请先在「RSSHub 帮助」页部署" placement="right">
                    <span>RSSHub 生成 <span style="color:#f56c6c">⚠ 不可用</span></span>
                  </el-tooltip>
                </template>
                <template v-else>
                  <span>RSSHub 生成</span>
                </template>
              </el-option>
              <el-option label="自动发现" value="auto" />
            </el-select>
            <el-tooltip :content="AUTO_DISCOVER_TOOLTIP" placement="top" :show-after="300">
              <el-icon class="help-icon"><QuestionFilled /></el-icon>
            </el-tooltip>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 自动发现结果弹窗 -->
    <el-dialog v-model="discoverDialogVisible" title="发现结果" width="500px">
      <div v-if="discoverResult">
        <el-alert :title="discoverResult.message" type="info" :closable="false" show-icon style="margin-bottom: 16px;" />

        <!-- 直接 RSS -->
        <div v-if="discoverResult.direct_rss.length > 0" style="margin-bottom: 16px;">
          <h4 style="margin-bottom: 8px;">发现 RSS 源：</h4>
          <el-radio-group v-model="selectedRssUrl" style="display: flex; flex-direction: column; gap: 8px;">
            <el-radio
              v-for="(rss, index) in discoverResult.direct_rss"
              :key="index"
              :value="rss.url"
            >
              {{ rss.url }}
            </el-radio>
          </el-radio-group>
        </div>

        <!-- RSSHub 数据库匹配提示（RSSHub 未运行时） -->
        <div v-if="discoverResult.rsshub_hint" style="margin-bottom: 16px;">
          <el-alert
            :title="discoverResult.rsshub_hint"
            type="warning"
            :closable="false"
            show-icon
          />
        </div>

        <!-- RSSHub 路由 -->
        <div v-if="discoverResult.rsshub_routes.length > 0">
          <h4 style="margin-bottom: 8px;">RSSHub 路由：</h4>
          <el-radio-group v-model="selectedRssUrl" style="display: flex; flex-direction: column; gap: 8px;">
            <el-radio
              v-for="(route, index) in discoverResult.rsshub_routes"
              :key="index"
              :value="route"
            >
              {{ route }}
            </el-radio>
          </el-radio-group>
        </div>
      </div>

      <template #footer>
        <el-button @click="discoverDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmDiscover" :disabled="!selectedRssUrl">确认使用</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, nextTick, computed } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { QuestionFilled } from '@element-plus/icons-vue'
import { request } from '@/api'
import { getRssSourceStatus } from '@/api/rss'
import RouteSelector from '@/components/rsshub/RouteSelector.vue'
import { validateAndFocusOnError, focusFirstErrorField } from '@/composables/useFormValidation'

// 自动发现 Tooltip 文案
const AUTO_DISCOVER_TOOLTIP = `自动发现：输入网站首页URL，系统自动检测该网站是否提供RSS订阅地址。

支持两种模式：
• 直接RSS：网站自带的RSS源
• RSSHub路由：需要RSSHub转化的网站（如Twitter、YouTube等）

适用场景：不知道目标网站的RSS地址时使用。`

interface RSSSource {
  id: number
  name: string
  url: string
  category: string | null
  source_type: 'standard' | 'rsshub' | 'auto'
  is_active: boolean
  rsshub_unavailable?: boolean
  fetch_error_count: number
  fetch_interval: number
  article_count: number
}

interface DiscoverResult {
  direct_rss: { url: string }[]
  rsshub_routes: string[]
  source_type: string | null
  message: string
  rsshub_hint?: string
}

// RSS源状态接口
interface RssSourceStatus {
  has_sources: boolean
  has_active_sources: boolean
  total_count: number
  active_count: number
}

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

const loading = ref(false)
const sources = ref<RSSSource[]>([])
const dialogVisible = ref(false)
const discoverDialogVisible = ref(false)
const submitting = ref(false)
const validating = ref(false)
const formRef = ref<FormInstance>()
const discoverResult = ref<DiscoverResult | null>(null)
const selectedRssUrl = ref<string>('')

// T-21: RSSHub 状态
const rsshubStatus = ref<RSSHubStatus | null>(null)
let rsshubPollingTimer: number | null = null

// 无活跃源警告状态
const rssStatus = ref<RssSourceStatus>({
  has_sources: false,
  has_active_sources: false,
  total_count: 0,
  active_count: 0,
})

// 是否显示无活跃源警告
const showWarning = computed(() => {
  return !rssStatus.value.has_active_sources
})

const form = reactive({
  name: '',
  url: '',
  category: '',
  source_type: 'standard' as 'standard' | 'rsshub' | 'auto',
  fetch_interval: 60,
})

const rules: FormRules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  url: [
    { required: true, message: '请输入URL', trigger: 'blur' },
    { type: 'url', message: '请输入有效的URL', trigger: 'blur' },
  ],
}

// URL 输入框占位符
const urlPlaceholder = computed(() => {
  if (form.source_type === 'auto') {
    return '请输入网站首页 URL，如 https://example.com'
  }
  return '请输入 RSS URL'
})

// T-21: RSSHub 状态相关计算属性
const isRSSHubRunning = computed(() => rsshubStatus.value?.status === 'running')

const rsshubAlertType = computed(() => {
  switch (rsshubStatus.value?.status) {
    case 'running': return 'success'
    case 'starting': return 'info'
    case 'docker_unavailable': return 'warning'
    case 'stopped':
    case 'error':
    default: return 'danger'
  }
})

const rsshubTagType = computed(() => {
  switch (rsshubStatus.value?.status) {
    case 'running': return 'success'
    case 'starting': return 'info'
    case 'docker_unavailable': return 'warning'
    case 'stopped':
    case 'error':
    default: return 'danger'
  }
})

const rsshubStatusLabel = computed(() => {
  switch (rsshubStatus.value?.status) {
    case 'running':
      return `运行中 · ${rsshubStatus.value.routes_count || 0} 条路由`
    case 'starting': return '启动中...'
    case 'docker_unavailable':
      return rsshubStatus.value?.message || 'Docker 环境不可用'
    case 'error': return '启动失败'
    case 'stopped':
    default: return '未运行'
  }
})

const rsshubBaseUrl = computed(() => rsshubStatus.value?.rsshub_url || 'http://localhost:1200')

// T-21: 获取 RSSHub 状态
async function fetchRSSHubStatus() {
  try {
    const data = await request.get<RSSHubStatus>('/rsshub/status')
    rsshubStatus.value = data
  } catch {
    rsshubStatus.value = {
      status: 'stopped',
      docker_available: false,
      rsshub_url: 'http://localhost:1200',
      message: '无法获取 RSSHub 状态',
    }
  }
}

// T-21: 启动 RSSHub 状态轮询
function startRSSHubPolling() {
  if (rsshubPollingTimer !== null) {
    clearInterval(rsshubPollingTimer)
  }
  fetchRSSHubStatus()
  rsshubPollingTimer = window.setInterval(fetchRSSHubStatus, 30000)
}

async function fetchSources() {
  loading.value = true
  try {
    const data = await request.get('/rss-sources/')
    sources.value = data.items || []
  } catch (error) {
    console.error('获取RSS源列表失败:', error)
  } finally {
    loading.value = false
  }
}

// 获取RSS源状态（用于判断是否显示警告）
async function fetchRssStatus() {
  try {
    rssStatus.value = await getRssSourceStatus()
  } catch (error) {
    console.error('获取RSS状态失败:', error)
  }
}

function showDialog() {
  dialogVisible.value = true
  form.name = ''
  form.url = ''
  form.category = ''
  form.source_type = 'standard'
  form.fetch_interval = 60
}

async function handleValidate() {
  if (!form.url) {
    ElMessage.warning('请先输入URL')
    return
  }

  // 如果是 auto 类型，调用自动发现接口
  if (form.source_type === 'auto') {
    await handleDiscover()
    return
  }

  validating.value = true
  try {
    const data = await request.post('/rss-sources/validate', { url: form.url })
    if (data.valid) {
      ElMessage.success(`校验通过！标题：${data.feed_title || '未知'}，文章数：${data.entry_count}`)
      if (!form.name && data.feed_title) {
        form.name = data.feed_title
      }
    } else {
      ElMessage.error(data.message)
    }
  } catch {
    ElMessage.error('校验请求失败')
  } finally {
    validating.value = false
  }
}

// 自动发现 RSS
async function handleDiscover() {
  if (!form.url) {
    ElMessage.warning('请先输入URL')
    return
  }

  validating.value = true
  try {
    const data = await request.post('/rss-sources/discover', { url: form.url })
    discoverResult.value = data

    if (data.direct_rss.length > 0) {
      selectedRssUrl.value = data.direct_rss[0].url
    } else if (data.rsshub_routes.length > 0) {
      selectedRssUrl.value = data.rsshub_routes[0]
    }

    discoverDialogVisible.value = true
  } catch {
    ElMessage.error('发现请求失败')
  } finally {
    validating.value = false
  }
}

// 确认发现结果
async function confirmDiscover() {
  if (!selectedRssUrl.value || !discoverResult.value) {
    return
  }

  // 更新表单
  form.url = selectedRssUrl.value

  // 根据发现结果设置 source_type
  if (discoverResult.value.rsshub_routes.includes(selectedRssUrl.value)) {
    form.source_type = 'rsshub'
  } else {
    form.source_type = 'standard'
  }

  // 如果名称为空，尝试获取
  if (!form.name) {
    try {
      const validateData = await request.post('/rss-sources/validate', {
        url: selectedRssUrl.value,
        source_type: form.source_type
      })
      if (validateData.valid && validateData.feed_title) {
        form.name = validateData.feed_title
      }
    } catch {
      // 忽略错误
    }
  }

  // 关闭发现弹窗，显示添加弹窗
  discoverDialogVisible.value = false
  ElMessage.success('已选择，请确认其他信息后保存')
}

async function handleSubmit() {
  if (!formRef.value) return

  // 验证表单，有效时执行提交
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) {
    // 验证失败，聚焦到第一个错误字段
    await nextTick()
    const dialogEl = document.querySelector('.rss-page .el-dialog')
    if (dialogEl) {
      focusFirstErrorField(dialogEl as HTMLElement)
    }
    return
  }

  // 如果是 auto 类型，先触发自动发现
  if (form.source_type === 'auto') {
    await handleDiscover()
    return
  }

  submitting.value = true
  try {
    // 直接保存（后端已包含校验逻辑）
    await request.post('/rss-sources/', form)
    ElMessage.success('添加成功')
    dialogVisible.value = false
    fetchSources()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '操作失败')
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row: RSSSource) {
  try {
    await request.delete(`/rss-sources/${row.id}`)
    ElMessage.success('删除成功')
    fetchSources()
  } catch (error) {
    ElMessage.error('删除失败')
  }
}

async function handleToggleActive(row: RSSSource) {
  try {
    await request.put(`/rss-sources/${row.id}`, {
      is_active: !row.is_active
    })
    ElMessage.success(row.is_active ? '已停用' : '已启用')
    fetchSources()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

onMounted(() => {
  fetchSources()
  fetchRssStatus()
  startRSSHubPolling()
})

onUnmounted(() => {
  if (rsshubPollingTimer !== null) {
    clearInterval(rsshubPollingTimer)
    rsshubPollingTimer = null
  }
})

// 源类型标签文本
function sourceTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    standard: '标准',
    rsshub: 'RSSHub',
    auto: '自动发现',
  }
  return labels[type] || type
}

// 源类型标签颜色
function sourceTypeTagType(type: string): string {
  const types: Record<string, string> = {
    standard: '',
    rsshub: 'warning',
    auto: 'success',
  }
  return types[type] || ''
}
</script>

<style scoped>
.rsshub-status-alert {
  margin-bottom: var(--spacing-md);
}

.no-active-source-alert {
  margin-bottom: var(--spacing-md);
}

.no-active-source-alert p {
  margin: 0 0 var(--spacing-sm) 0;
}

.status-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.status-help-link {
  margin-left: var(--spacing-md);
}

.status-help-link a {
  color: var(--el-color-primary);
  text-decoration: none;
}

.status-help-link a:hover {
  text-decoration: underline;
}

.rsshub-warning-tag {
  cursor: pointer;
}

.route-selector-wrapper {
  margin-top: var(--spacing-sm);
}

.rss-page { padding: 0; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.interval-unit { margin-left: var(--spacing-sm); color: var(--color-text-muted); }
.empty-alert { margin-bottom: var(--spacing-md); }
.text-danger { color: var(--el-color-danger); font-weight: 500; }

/* 源类型表单项 wrapper - 让 select 和问号图标水平排列 */
.source-type-wrapper {
  display: flex;
  align-items: center;
  width: 100%;
}

/* 问号图标样式 */
.help-icon {
  margin-left: 8px;
  color: var(--el-color-info);
  cursor: pointer;
  font-size: 16px;
}

/* URL 输入框下方的提示文字 */
.url-hint {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.rsshub-status-desc {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
}
</style>
