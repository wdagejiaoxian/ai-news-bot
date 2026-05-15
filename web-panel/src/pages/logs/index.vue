<template>
  <div class="logs-page">
    <el-card shadow="never">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="操作日志" name="operation">
          <template #label>
            <span><el-icon><DocumentCopy /></el-icon> 操作日志</span>
          </template>

          <div class="tab-toolbar">
            <el-button size="small" @click="fetchLogs">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
          </div>

          <el-table
            v-loading="loading"
            :data="logs"
            style="width: 100%"
          >
        <!-- 操作人（复用 username 字段显示 operator） -->
        <el-table-column prop="operator" label="操作人" width="120">
          <template #default="{ row }">
            {{ row.operator || '-' }}
          </template>
        </el-table-column>

        <!-- 操作类型 -->
        <el-table-column prop="action" label="操作" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="getActionTagType(row.action)">
              {{ getActionText(row.action) }}
            </el-tag>
          </template>
        </el-table-column>

        <!-- 日志类型（复用 resource_type 字段显示 log_type） -->
        <el-table-column prop="log_type" label="日志类型" width="120">
          <template #default="{ row }">
            {{ getResourceTypeText(row.log_type) }}
          </template>
        </el-table-column>

        <!-- 任务名称（复用 resource_id 字段显示 task_name） -->
        <el-table-column prop="task_name" label="任务名称" width="180">
          <template #default="{ row }">
            {{ row.task_name || '-' }}
          </template>
        </el-table-column>

        <!-- 详情 -->
        <el-table-column prop="detail" label="详情" min-width="300">
          <template #default="{ row }">
            <el-tooltip
              :content="formatDetail(row.detail)"
              placement="top"
              :show-after="500"
            >
              <div class="detail-preview">{{ formatDetail(row.detail) }}</div>
            </el-tooltip>
          </template>
        </el-table-column>

        <!-- IP地址 -->
        <el-table-column prop="ip_address" label="IP地址" width="140">
          <template #default="{ row }">
            {{ row.ip_address || '-' }}
          </template>
        </el-table-column>

        <!-- 操作时间 -->
        <el-table-column prop="created_at" label="操作时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>

        <!-- 操作 -->
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="showLogDetail(row)">
              详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 空状态 -->
      <div v-if="!loading && logs.length === 0" class="empty-state">
        <div class="empty-state__icon">
          <el-icon :size="32"><Document /></el-icon>
        </div>
        <div class="empty-state__title">暂无操作日志</div>
        <div class="empty-state__desc">用户操作日志将在有操作记录后显示在这里</div>
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

      <!-- 操作日志详情弹窗 -->
      <el-dialog v-model="detailVisible" title="操作日志详情" width="700px" append-to-body :close-on-click-modal="false" :destroy-on-close="false">
        <template v-if="currentLog">
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="操作人">
              {{ currentLog.operator || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="操作时间">
              {{ formatDate(currentLog.created_at) }}
            </el-descriptions-item>
            <el-descriptions-item label="操作类型">
              <el-tag :type="getActionTagType(currentLog.action)" size="small">
                {{ getActionText(currentLog.action) }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="日志类型">
              {{ getResourceTypeText(currentLog.log_type) }}
            </el-descriptions-item>
            <el-descriptions-item label="任务名称">
              {{ currentLog.task_name || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="IP地址">
              {{ currentLog.ip_address || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="日志级别">
              {{ currentLog.log_level || '-' }}
            </el-descriptions-item>
          </el-descriptions>
          <el-divider />
          <div class="detail-section">
            <div class="detail-section__title">详细内容</div>
            <el-input
              type="textarea"
              :rows="10"
              :model-value="formatDetailJson(currentLog.detail)"
              readonly
              class="detail-json-input"
            />
          </div>
        </template>
      </el-dialog>
        </el-tab-pane>

        <el-tab-pane label="推送日志" name="push">
          <template #label>
            <span><el-icon><Promotion /></el-icon> 推送日志</span>
          </template>
          <PushLogs />
        </el-tab-pane>

        <el-tab-pane label="任务执行历史" name="task">
          <template #label>
            <span><el-icon><Timer /></el-icon> 任务执行历史</span>
          </template>
          <TaskExecutionHistory />
        </el-tab-pane>

        <el-tab-pane label="系统日志" name="file">
          <template #label>
            <span><el-icon><Document /></el-icon> 系统日志</span>
          </template>
          <FileLogViewer />
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { request } from '@/api'
import dayjs from 'dayjs'
import TaskExecutionHistory from './components/TaskExecutionHistory.vue'
import PushLogs from './components/PushLogs.vue'
import FileLogViewer from './components/FileLogViewer.vue'

interface OperationLog {
  id: number
  log_type: string
  log_level: string
  task_name: string | null
  operator: string
  action: string
  detail: Record<string, any> | null
  ip_address: string | null
  created_at: string | null
}

const loading = ref(false)
const logs = ref<OperationLog[]>([])
const detailVisible = ref(false)
const currentLog = ref<OperationLog | null>(null)

const activeTab = ref('operation')

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0,
})

function formatDate(date: string | null) {
  return date ? dayjs(date).format('YYYY-MM-DD HH:mm:ss') : '-'
}

function formatDetail(detail: Record<string, any> | null) {
  if (!detail) return '-'
  // 如果是对象，转换为易读的字符串
  if (typeof detail === 'object') {
    // 尝试提取关键字段显示
    if (detail.message) return detail.message
    if (detail.error) return `错误: ${detail.error}`
    if (detail.duration_ms) return `耗时: ${detail.duration_ms}ms`
    if (detail.articles_count !== undefined) return `处理: ${detail.articles_count} 篇`
    if (detail.changes) return `变更: ${detail.changes.length} 个字段`
    return JSON.stringify(detail)
  }
  return String(detail)
}

function formatDetailJson(detail: Record<string, any> | null) {
  if (!detail) return '暂无详细内容'
  try {
    return JSON.stringify(detail, null, 2)
  } catch {
    return String(detail)
  }
}

function showLogDetail(log: OperationLog) {
  currentLog.value = log
  detailVisible.value = true
}

function getActionTagType(action: string) {
  switch (action) {
    case 'success':
      return 'success'
    case 'fail':
    case 'error':
      return 'danger'
    case 'start':
      return 'primary'
    case 'reload':
      return 'warning'
    default:
      return 'info'
  }
}

function getActionText(action: string) {
  const map: Record<string, string> = {
    // 配置变更相关
    create: '创建',
    update: '更新',
    delete: '删除',
    reload: '热重载',
    // 任务执行相关
    start: '开始',
    success: '成功',
    fail: '失败',
    // 其他
    login: '登录',
  }
  return map[action] || action
}

function getResourceTypeText(type: string) {
  const map: Record<string, string> = {
    // 已有映射
    rss_source: 'RSS源',
    article: '文章',
    config: '配置',
    user: '用户',
    // 日志类型映射（复用了 resource_type 字段）
    config_change: '配置变更',
    task_exec: '任务执行',
    system: '系统',
  }
  return map[type] || type
}

async function fetchLogs() {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
    }

    const data: any = await request.get('/admin/logs', { params })
    // 响应拦截器已返回 data.data，直接使用
    logs.value = data.items || []
    pagination.total = data.total || 0
  } catch (error) {
    console.error('获取操作日志失败:', error)
  } finally {
    loading.value = false
  }
}

function handleSizeChange(size: number) {
  pagination.pageSize = size
  pagination.page = 1
  fetchLogs()
}

function handlePageChange(page: number) {
  pagination.page = page
  fetchLogs()
}

onMounted(() => {
  fetchLogs()
})
</script>

<style scoped>
.logs-page {
  padding: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.tab-toolbar {
  margin-bottom: 12px;
  display: flex;
  justify-content: flex-end;
}

.detail-preview {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 300px;
  color: var(--color-text-secondary);
}

.pagination-wrapper {
  margin-top: var(--spacing-lg);
  display: flex;
  justify-content: flex-end;
}

.detail-section {
  margin-top: 4px;
}

.detail-section__title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--color-text-primary);
}

.detail-json-input {
  font-family: 'Courier New', Courier, monospace;
  font-size: 13px;
  line-height: 1.5;
}

.detail-json-input .el-textarea__inner {
  font-family: 'Courier New', Courier, monospace;
  background-color: var(--color-bg-secondary, #f5f7fa);
  color: var(--color-text-primary);
  resize: vertical;
  min-height: 200px;
}

:deep(.el-descriptions__body) {
  background-color: var(--color-bg-primary);
}

:deep(.el-descriptions__label) {
  font-weight: 500;
  width: 100px;
}
</style>
