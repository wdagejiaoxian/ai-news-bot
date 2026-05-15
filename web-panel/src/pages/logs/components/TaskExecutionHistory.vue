<template>
  <div class="task-execution-history">
    <!-- 筛选区域 -->
    <div class="filter-bar">
      <el-form :inline="true" size="small">
        <el-form-item label="任务名称">
          <el-select
            v-model="filters.task_name"
            clearable
            placeholder="全部任务"
            style="width: 160px"
          >
            <el-option
              v-for="t in taskOptions"
              :key="t.value"
              :label="t.label"
              :value="t.value"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="状态">
          <el-select
            v-model="filters.status"
            clearable
            placeholder="全部状态"
            style="width: 120px"
          >
            <el-option label="成功" value="success" />
            <el-option label="失败" value="fail" />
            <el-option label="进行中" value="start" />
            <el-option label="超时" value="timeout" />
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
          <el-button type="primary" @click="handleQuery">
            查询
          </el-button>
          <el-button @click="handleReset">
            重置
          </el-button>
          <el-button @click="fetchData">
            <el-icon><Refresh /></el-icon>
          </el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 统计概览 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-value">{{ stats.total_executions }}</div>
          <div class="stat-label">总执行次数</div>
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
          <div class="stat-value">{{ formatDuration(stats.avg_duration_ms) }}</div>
          <div class="stat-label">平均耗时</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-value">{{ stats.fail_count + stats.timeout_count }}</div>
          <div class="stat-label">异常次数</div>
        </div>
      </el-col>
    </el-row>

    <!-- 执行时长趋势 -->
    <div class="trend-section">
      <div class="trend-section__header">
        <span class="trend-section__title">执行时长趋势</span>
        <el-select
          v-model="trendTaskName"
          size="small"
          style="width: 160px"
          @change="fetchTrend"
        >
          <el-option
            v-for="t in taskOptions"
            :key="t.value"
            :label="t.label"
            :value="t.value"
          />
        </el-select>
      </div>
      <div v-if="trendLoading" class="trend-loading">加载中...</div>
      <div
        v-else-if="trendData.length === 0"
        class="trend-empty"
      >
        暂无趋势数据，请等待任务执行后再查看
      </div>
      <VChart
        v-else
        :option="chartOption"
        autoresize
        style="height: 220px"
      />
    </div>

    <!-- 表格 -->
    <el-table
      v-loading="loading"
      :data="records"
      style="width: 100%"
      empty-text="暂无任务执行记录"
    >
      <!-- 展开行 -->
      <el-table-column type="expand" width="40">
        <template #default="{ row }">
          <div class="expanded-detail">
            <div class="expanded-detail__row">
              <span class="expanded-detail__label">任务名称</span>
              <span class="expanded-detail__value">{{ row.task_name }}</span>
            </div>
            <div v-if="row.result" class="expanded-detail__row">
              <span class="expanded-detail__label">执行结果</span>
              <pre class="expanded-detail__pre">{{ formatResult(row.result) }}</pre>
            </div>
            <div v-if="row.error_message" class="expanded-detail__row">
              <span class="expanded-detail__label text-danger-label">错误信息</span>
              <pre class="expanded-detail__pre expanded-detail__pre--error">{{ row.error_message }}</pre>
            </div>
            <div class="expanded-detail__row">
              <span class="expanded-detail__label">开始时间</span>
              <span class="expanded-detail__value">{{ formatDate(row.start_time) }}</span>
            </div>
            <div v-if="row.end_time" class="expanded-detail__row">
              <span class="expanded-detail__label">结束时间</span>
              <span class="expanded-detail__value">{{ formatDate(row.end_time) }}</span>
            </div>
          </div>
        </template>
      </el-table-column>

      <el-table-column
        prop="task_name"
        label="任务名称"
        width="160"
        show-overflow-tooltip
      />

      <el-table-column label="状态" width="100" align="center">
        <template #default="{ row }">
          <el-tag
            :type="statusTagType(row.status)"
            size="small"
            effect="dark"
          >
            {{ statusText(row.status) }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column label="开始时间" width="180">
        <template #default="{ row }">
          {{ formatDate(row.start_time) }}
        </template>
      </el-table-column>

      <el-table-column label="耗时" width="100">
        <template #default="{ row }">
          <span :class="durationClass(row.duration_ms)">
            {{ formatDuration(row.duration_ms) }}
          </span>
        </template>
      </el-table-column>

      <el-table-column
        prop="result"
        label="结果摘要"
        min-width="200"
        show-overflow-tooltip
      />

      <el-table-column
        label="错误信息"
        min-width="200"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          <span v-if="row.error_message" class="text-danger">
            {{ row.error_message }}
          </span>
          <span v-else>-</span>
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
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import dayjs from 'dayjs'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  GridComponent,
} from 'echarts/components'
import VChart from 'vue-echarts'
import {
  getTaskExecutionHistory,
  getTaskExecutionStats,
  getDurationTrend,
  type TaskExecutionRecord,
  type TaskExecutionStats,
} from '@/api/task-execution-history'
import { useTheme } from '@/composables/useTheme'

use([CanvasRenderer, LineChart, TitleComponent, TooltipComponent, GridComponent])

const { isDark } = useTheme()

/** 任务名称选项（与后端 TASK_NAME_MAP 保持一致） */
const taskOptions = [
  { value: 'fetch_ai_news', label: '采集AI资讯' },
  { value: 'fetch_github_trending', label: '采集GitHub热门' },
  { value: 'fetch_weekly_github_trending', label: '采集GitHub周热门' },
  { value: 'send_daily_report', label: '发送日报' },
  { value: 'send_weekly_report', label: '发送周报' },
  { value: 'process_pending_content', label: '处理待处理内容' },
  { value: 'cleanup_low_score_articles', label: '清理低分文章' },
  { value: 'cleanup_expired_data', label: '清理过期数据' },
  { value: 'cluster_topics', label: '主题聚类' },
  { value: 'reindex_vectors', label: '向量对账' },
]

const loading = ref(false)
const records = ref<TaskExecutionRecord[]>([])
const stats = ref<TaskExecutionStats>({
  total_executions: 0,
  success_count: 0,
  fail_count: 0,
  timeout_count: 0,
  success_rate: 0,
  avg_duration_ms: 0,
  max_duration_ms: 0,
  min_duration_ms: 0,
  by_task: [],
})

const filters = reactive({
  task_name: undefined as string | undefined,
  status: undefined as string | undefined,
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

/** 格式化时长：ms → 可读格式 */
function formatDuration(ms: number | null) {
  if (ms === null || ms === undefined) return '-'
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  const min = Math.floor(ms / 60000)
  const sec = Math.round((ms % 60000) / 1000)
  return `${min}m${sec}s`
}

/** 状态对应 el-tag 类型 */
function statusTagType(status: string) {
  switch (status) {
    case 'success': return 'success'
    case 'fail': return 'danger'
    case 'timeout': return 'warning'
    case 'start': return 'info'
    default: return 'info'
  }
}

/** 状态中文文本 */
function statusText(status: string) {
  switch (status) {
    case 'success': return '成功'
    case 'fail': return '失败'
    case 'timeout': return '超时'
    case 'start': return '进行中'
    default: return status
  }
}

/** 耗时 > 60s 标红 */
function durationClass(ms: number | null) {
  if (ms !== null && ms > 60000) return 'text-danger'
  return ''
}

/** 格式化执行结果：尝试将 JSON 字符串格式化为缩进文本 */
function formatResult(result: string | null) {
  if (!result) return '-'
  try {
    const parsed = JSON.parse(result)
    return JSON.stringify(parsed, null, 2)
  } catch {
    return result
  }
}

// ========== 趋势图表 ==========

const trendTaskName = ref('fetch_ai_news')
const trendLoading = ref(false)
const trendData = ref<Array<{date: string; avg_duration_ms: number; count: number}>>([])

/** 暗黑模式感知的图表主题色 */
const chartColors = computed(() => ({
  text: isDark.value ? '#8e8e93' : '#45515e',
  splitLine: isDark.value ? '#2f3842' : '#e5e7eb',
  primary: '#409eff',
  primaryBg: isDark.value ? 'rgba(64, 158, 255, 0.15)' : 'rgba(64, 158, 255, 0.25)',
  primaryBgFade: isDark.value ? 'rgba(64, 158, 255, 0.01)' : 'rgba(64, 158, 255, 0.02)',
}))

const chartOption = computed(() => ({
  tooltip: {
    trigger: 'axis' as const,
    formatter: (params: any) => {
      const p = params[0]
      const raw = trendData.value[p.dataIndex]
      if (!raw) return ''
      return `<div>
        <div><b>${raw.date}</b></div>
        <div>平均耗时: ${formatDuration(raw.avg_duration_ms)}</div>
        <div>执行次数: ${raw.count} 次</div>
      </div>`
    },
  },
  grid: { left: 50, right: 20, top: 10, bottom: 25 },
  xAxis: {
    type: 'category' as const,
    data: trendData.value.map(d => d.date.slice(5)), // MM-DD
    axisLabel: { fontSize: 11, color: chartColors.value.text },
    axisLine: { lineStyle: { color: chartColors.value.splitLine } },
  },
  yAxis: {
    type: 'value' as const,
    name: '耗时(ms)',
    nameTextStyle: { fontSize: 11, color: chartColors.value.text },
    axisLabel: { fontSize: 11, color: chartColors.value.text },
    splitLine: { lineStyle: { type: 'dashed' as const, color: chartColors.value.splitLine } },
  },
  series: [{
    data: trendData.value.map(d => d.avg_duration_ms),
    type: 'line' as const,
    smooth: true,
    symbol: 'circle',
    symbolSize: 6,
    areaStyle: {
      color: {
        type: 'linear' as const,
        x: 0, y: 0, x2: 0, y2: 1,
        colorStops: [
          { offset: 0, color: chartColors.value.primaryBg },
          { offset: 1, color: chartColors.value.primaryBgFade },
        ],
      },
    },
    lineStyle: { width: 2, color: chartColors.value.primary },
    itemStyle: { color: chartColors.value.primary },
  }],
}))

async function fetchTrend() {
  trendLoading.value = true
  try {
    const result = await getDurationTrend({
      task_name: trendTaskName.value,
      days: 30,
    })
    trendData.value = result.trend || []
  } catch (e) {
    console.error('获取时长趋势失败:', e)
    trendData.value = []
  } finally {
    trendLoading.value = false
  }
}

/** 获取数据 */
async function fetchData() {
  loading.value = true
  try {
    const params: Record<string, any> = {
      page: pagination.page,
      page_size: pagination.page_size,
    }
    if (filters.task_name) params.task_name = filters.task_name
    if (filters.status) params.status = filters.status
    if (dateRange.value) {
      params.start_date = dateRange.value[0]
      params.end_date = dateRange.value[1]
    }

    const [historyRes, statsRes] = await Promise.all([
      getTaskExecutionHistory(params),
      getTaskExecutionStats({
        task_name: filters.task_name,
        days: 30,
      }),
    ])

    records.value = historyRes.items
    pagination.total = historyRes.total
    stats.value = statsRes
  } catch (e) {
    console.error('获取任务执行历史失败:', e)
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

/** 重置 */
function handleReset() {
  filters.task_name = undefined
  filters.status = undefined
  dateRange.value = null
  pagination.page = 1
  fetchData()
}

onMounted(() => {
  fetchData()
  fetchTrend()
})
</script>

<style scoped>
.task-execution-history {
  padding: 0;
}

.filter-bar {
  margin-bottom: 16px;
}

.stat-row {
  margin-bottom: 16px;
}

.stat-card {
  background: var(--el-fill-color-light, #f5f7fa);
  border-radius: 8px;
  padding: 16px;
  text-align: center;
}

.stat-value {
  font-size: 24px;
  font-weight: 600;
  color: var(--color-text-primary, #303133);
  line-height: 1.4;
}

.stat-label {
  font-size: 13px;
  color: var(--color-text-secondary, #909399);
  margin-top: 4px;
}

.text-success {
  color: var(--el-color-success, #67c23a);
}

.text-danger {
  color: var(--el-color-danger, #f56c6c);
}

.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

/* 展开行详情 */
.expanded-detail {
  padding: 12px 24px;
}

.expanded-detail__row {
  margin-bottom: 10px;
  display: flex;
  flex-direction: column;
}

.expanded-detail__row:last-child {
  margin-bottom: 0;
}

.expanded-detail__label {
  font-size: 12px;
  color: var(--color-text-secondary, #909399);
  margin-bottom: 4px;
  font-weight: 500;
}

.text-danger-label {
  color: var(--el-color-danger, #f56c6c);
}

.expanded-detail__value {
  font-size: 14px;
  color: var(--color-text-primary, #303133);
}

.expanded-detail__pre {
  font-size: 13px;
  background: var(--el-fill-color-light, #f5f7fa);
  padding: 10px 14px;
  border-radius: 4px;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
  line-height: 1.5;
  max-height: 200px;
  overflow-y: auto;
  font-family: 'Courier New', Courier, monospace;
}

.expanded-detail__pre--error {
  color: var(--el-color-danger, #f56c6c);
  background: var(--el-color-danger-light-9, #fef0f0);
}

/* 趋势图表 */
.trend-section {
  margin-bottom: 16px;
  padding: 16px;
  background: var(--el-fill-color-extra-light, #fafafa);
  border-radius: 8px;
  border: 1px solid var(--el-border-color-light, #ebeef5);
}

.trend-section__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.trend-section__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary, #303133);
}

.trend-loading,
.trend-empty {
  height: 100px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-secondary, #909399);
  font-size: 13px;
}
</style>
