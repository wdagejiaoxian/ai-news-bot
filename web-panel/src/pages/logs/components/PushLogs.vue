<template>
  <div class="push-logs">
    <!-- 筛选区域 -->
    <div class="filter-bar">
      <el-form :inline="true" size="small">
        <el-form-item label="推送平台">
          <el-select
            v-model="filters.platform"
            clearable
            placeholder="全部平台"
            style="width: 140px"
          >
            <el-option label="企业微信" value="wecom" />
            <el-option label="Git" value="git" />
            <el-option label="Obsidian本地" value="obsidian_local" />
          </el-select>
        </el-form-item>

        <el-form-item label="推送类型">
          <el-select
            v-model="filters.push_type"
            clearable
            placeholder="全部类型"
            style="width: 140px"
          >
            <el-option label="即时推送" value="immediate" />
            <el-option label="日报" value="daily" />
            <el-option label="周报" value="weekly" />
          </el-select>
        </el-form-item>

        <el-form-item label="状态">
          <el-select
            v-model="filters.is_success"
            clearable
            placeholder="全部状态"
            style="width: 120px"
          >
            <el-option label="成功" :value="true" />
            <el-option label="失败" :value="false" />
          </el-select>
        </el-form-item>

        <el-form-item label="时间范围">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            style="width: 240px"
          />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="handleQuery">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
          <el-button @click="fetchData"><el-icon><Refresh /></el-icon></el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 统计概览 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-value">{{ stats.total }}</div>
          <div class="stat-label">总推送数</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-value" :class="stats.success_rate >= 90 ? 'text-success' : 'text-danger'">
            {{ stats.success_rate }}%
          </div>
          <div class="stat-label">成功率</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-value">{{ stats.today }}</div>
          <div class="stat-label">今日推送</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-value">{{ stats.fail_count }}</div>
          <div class="stat-label">失败次数</div>
        </div>
      </el-col>
    </el-row>

    <!-- 数据表格 -->
    <el-table
      v-loading="loading"
      :data="records"
      style="width: 100%"
      empty-text="暂无推送日志"
    >
      <el-table-column label="推送时间" width="170">
        <template #default="{ row }">{{ formatDate(row.pushed_at) }}</template>
      </el-table-column>

      <el-table-column prop="webhook_config_name" label="Webhook" width="150" show-overflow-tooltip />

      <el-table-column prop="platform" label="平台" width="90">
        <template #default="{ row }">{{ platformText(row.platform) }}</template>
      </el-table-column>

      <el-table-column prop="push_type" label="类型" width="80">
        <template #default="{ row }">{{ pushTypeText(row.push_type) }}</template>
      </el-table-column>

      <el-table-column prop="content" label="内容预览" min-width="200" show-overflow-tooltip />

      <el-table-column label="状态" width="80" align="center">
        <template #default="{ row }">
          <el-tag :type="row.is_success ? 'success' : 'danger'" size="small" effect="dark">
            {{ row.is_success ? '成功' : '失败' }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column label="HTTP状态码" width="100">
        <template #default="{ row }">{{ row.http_status_code || '-' }}</template>
      </el-table-column>

      <el-table-column label="操作" width="80" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="primary" link @click="showDetail(row)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <div v-if="pagination.total > 0" class="pagination-wrapper">
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.page_size"
        :page-sizes="[10, 20, 50]"
        :total="pagination.total"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="handlePageChange"
        @current-change="handlePageChange"
      />
    </div>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" title="推送日志详情" width="700px" append-to-body :close-on-click-modal="false" :destroy-on-close="false">
      <template v-if="currentLog">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="Webhook名称">
            {{ currentLog.webhook_config_name || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="推送时间">
            {{ formatDate(currentLog.pushed_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="推送平台">
            {{ platformText(currentLog.platform) }}
          </el-descriptions-item>
          <el-descriptions-item label="推送类型">
            {{ pushTypeText(currentLog.push_type) }}
          </el-descriptions-item>
          <el-descriptions-item label="推送状态">
            <el-tag :type="currentLog.is_success ? 'success' : 'danger'" size="small" effect="dark">
              {{ currentLog.is_success ? '成功' : '失败' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="HTTP状态码">
            {{ currentLog.http_status_code || '-' }}
          </el-descriptions-item>
          <el-descriptions-item v-if="currentLog.error_message" label="错误信息" :span="2">
            <span class="text-danger">{{ currentLog.error_message }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="关联文章ID">
            {{ currentLog.article_id || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="关联GitHub项目ID">
            {{ currentLog.github_repo_id || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="Obsidian文件路径" :span="2">
            {{ currentLog.obsidian_file_path || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="Git提交SHA" :span="2">
            {{ currentLog.git_commit_sha || '-' }}
          </el-descriptions-item>
        </el-descriptions>
        <el-divider />
        <div class="detail-section">
          <div class="detail-section__title">推送内容</div>
          <el-input
            type="textarea"
            :rows="8"
            :model-value="currentLog.content || '暂无内容'"
            readonly
            class="detail-textarea"
          />
          <div v-if="currentLog.content && currentLog.content.length >= 500" class="detail-section__tip">
            注：推送内容在写入时截断至 500 字符，以上为截断后的内容
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import dayjs from 'dayjs'
import {
  getPushLogs,
  getPushLogsStats,
  type PushLogRecord,
  type PushLogStats,
} from '@/api/push_logs'

const loading = ref(false)
const records = ref<PushLogRecord[]>([])
const stats = ref<PushLogStats>({
  total: 0,
  success_count: 0,
  fail_count: 0,
  success_rate: 0,
  today: 0,
  by_platform: {},
})

const detailVisible = ref(false)
const currentLog = ref<PushLogRecord | null>(null)

const filters = reactive({
  platform: undefined as string | undefined,
  push_type: undefined as string | undefined,
  is_success: undefined as boolean | undefined,
})

const dateRange = ref<[string, string] | null>(null)

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0,
})

/** 格式化日期 */
function formatDate(date: string | null) {
  return date ? dayjs(date).format('YYYY-MM-DD HH:mm:ss') : '-'
}

/** 平台中文名 */
function platformText(platform: string | null) {
  const map: Record<string, string> = {
    wecom: '企业微信',
    git: 'Git',
    obsidian_local: 'Obsidian本地',
  }
  return map[platform ?? ''] || platform || '-'
}

/** 推送类型中文名 */
function pushTypeText(type: string | null) {
  const map: Record<string, string> = {
    immediate: '即时推送',
    daily: '日报',
    weekly: '周报',
  }
  return map[type ?? ''] || type || '-'
}

/** 显示详情弹窗 */
function showDetail(log: PushLogRecord) {
  currentLog.value = log
  detailVisible.value = true
}

/** 获取数据（列表 + 统计并行） */
async function fetchData() {
  loading.value = true
  try {
    const params: Record<string, any> = {
      page: pagination.page,
      page_size: pagination.page_size,
    }
    if (filters.platform) params.platform = filters.platform
    if (filters.push_type) params.push_type = filters.push_type
    if (filters.is_success !== undefined) params.is_success = filters.is_success
    if (dateRange.value) {
      params.start_date = dateRange.value[0]
      params.end_date = dateRange.value[1]
    }

    const [listRes, statsRes] = await Promise.all([
      getPushLogs(params),
      getPushLogsStats({ days: 30 }),
    ])

    records.value = listRes.items
    pagination.total = listRes.total
    stats.value = statsRes
  } catch (e) {
    console.error('获取推送日志失败:', e)
  } finally {
    loading.value = false
  }
}

/** 分页切换 */
function handlePageChange() {
  fetchData()
}

/** 查询 */
function handleQuery() {
  pagination.page = 1
  fetchData()
}

/** 重置筛选 */
function handleReset() {
  filters.platform = undefined
  filters.push_type = undefined
  filters.is_success = undefined
  dateRange.value = null
  pagination.page = 1
  fetchData()
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.push-logs {
  padding: 0;
}

.filter-bar {
  margin-bottom: var(--spacing-md);
}

.stat-row {
  margin-bottom: var(--spacing-lg);
}

.stat-card {
  text-align: center;
  padding: 16px 12px;
  background: var(--el-fill-color-light, #f0f2f5);
  border-radius: 8px;
  transition: background-color 0.2s;
}

.stat-card:hover {
  background: var(--el-fill-color, #e8eaed);
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  line-height: 1.2;
  margin-bottom: 4px;
}

.stat-label {
  font-size: 13px;
  color: var(--color-text-secondary, #909399);
}

.text-success {
  color: var(--el-color-success, #67c23a);
}

.text-danger {
  color: var(--el-color-danger, #f56c6c);
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

.detail-section__tip {
  font-size: 12px;
  color: var(--el-color-warning, #e6a23c);
  margin-top: 6px;
}

.detail-textarea {
  font-size: 13px;
  line-height: 1.5;
}

.detail-textarea .el-textarea__inner {
  background-color: var(--color-bg-secondary, #f5f7fa);
  color: var(--color-text-primary);
  resize: vertical;
  min-height: 150px;
}

/* 弹窗响应式适配 */
@media (max-width: 768px) {
  :deep(.el-dialog) {
    width: 92% !important;
    max-width: 92% !important;
    margin: 10px auto !important;
  }

  :deep(.el-dialog__body) {
    padding: 16px !important;
  }

  :deep(.el-descriptions) {
    table-layout: fixed !important;
  }

  :deep(.el-descriptions__cell) {
    word-break: break-all;
  }
}
</style>
