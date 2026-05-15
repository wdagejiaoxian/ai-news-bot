<template>
  <div class="scheduler-page">
    <!-- 运行时任务状态 -->
    <el-card shadow="never" class="jobs-card">
      <template #header>
        <div class="card-header">
          <span>定时任务状态</span>
          <el-button type="primary" link @click="fetchJobs">
            刷新
          </el-button>
        </div>
      </template>

      <el-table v-loading="loading" :data="jobs" style="width: 100%">
        <el-table-column prop="id" label="任务ID" min-width="120" show-overflow-tooltip />
        <el-table-column prop="name" label="任务名称" min-width="120" show-overflow-tooltip />
        <el-table-column prop="trigger" label="触发方式" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">
            {{ formatTrigger(row.trigger) }}
          </template>
        </el-table-column>
        <el-table-column prop="next_run_time" label="下次执行时间" min-width="130" show-overflow-tooltip>
          <template #default="{ row }">
            {{ formatDate(row.next_run_time) }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="row.status === 'active' ? 'success' : 'info'">
              {{ row.status === 'active' ? '运行中' : '已停止' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right" align="center">
          <template #default="{ row }">
            <el-button type="primary" link size="small" :loading="triggeringId === row.id" @click="handleTrigger(row)">
              立即执行
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 空状态 -->
      <div v-if="!loading && jobs.length === 0" class="empty-state">
        <div class="empty-state__icon">
          <el-icon :size="32"><Clock /></el-icon>
        </div>
        <div class="empty-state__title">暂无运行中的任务</div>
        <div class="empty-state__desc">系统任务将在配置后自动显示在这里</div>
      </div>
    </el-card>

    <!-- 任务配置管理 -->
    <el-card shadow="never" class="configs-card">
      <template #header>
        <div class="card-header">
          <span>任务配置</span>
          <el-button type="primary" link @click="fetchConfigs">
            刷新
          </el-button>
        </div>
      </template>

      <el-table v-loading="configsLoading" :data="configs" style="width: 100%">
        <el-table-column prop="task_name" label="任务ID" min-width="140" show-overflow-tooltip />
        <el-table-column prop="task_type" label="触发模式" width="110" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="row.task_type === 'interval' ? 'warning' : 'success'">
              {{ row.task_type === 'interval' ? '间隔触发' : '固定时间' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="触发时间" min-width="120">
          <template #default="{ row }">
            <span class="cell-text">
              <span v-if="row.task_type === 'interval'">
                每 {{ row.interval_minutes }} 分钟
              </span>
              <span v-else>
                {{ formatFixedTime(row) }}
              </span>
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="next_run" label="下次执行" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">
            {{ formatDate(row.next_run) }}
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="启用状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="row.is_active ? 'success' : 'danger'">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right" align="center">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="openEditDialog(row)">
              编辑
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 空状态 -->
      <div v-if="!configsLoading && configs.length === 0" class="empty-state">
        <div class="empty-state__icon">
          <el-icon :size="32"><Setting /></el-icon>
        </div>
        <div class="empty-state__title">暂无任务配置</div>
        <div class="empty-state__desc">任务配置将在系统设置后自动显示</div>
      </div>
    </el-card>

    <!-- 编辑配置对话框 -->
    <el-dialog v-model="editDialogVisible" title="编辑任务配置" width="500px">
      <el-form v-if="currentConfig" :model="editForm" label-width="120px">
        <el-form-item label="任务名称">
          <el-input v-model="currentConfig.task_name" disabled />
        </el-form-item>
        <el-form-item label="触发模式">
          <el-radio-group v-model="editForm.task_type">
            <el-radio-button value="interval" :disabled="isFixedForced">间隔触发</el-radio-button>
            <el-radio-button value="fixed" :disabled="isIntervalForced">固定时间</el-radio-button>
          </el-radio-group>
          <div v-if="isIntervalForced" class="form-tip">此任务只能使用间隔触发模式</div>
          <div v-if="isFixedForced" class="form-tip">此任务只能使用固定时间触发模式</div>
        </el-form-item>

        <!-- 间隔触发配置 -->
        <template v-if="editForm.task_type === 'interval'">
          <el-form-item label="间隔分钟数">
            <el-input-number
              v-model="editForm.interval_minutes"
              :min="intervalMin"
              :max="intervalMax"
              :step="5"
            />
            <span class="form-tip">最小值: {{ intervalMin }}分钟</span>
          </el-form-item>
          <el-alert
            v-if="intervalConstraint"
            :title="intervalConstraint"
            type="warning"
            :closable="false"
            show-icon
            class="constraint-alert"
          />
        </template>

        <!-- 固定时间配置 -->
        <template v-else>
          <el-form-item label="执行时间">
            <el-time-picker
              v-model="editForm.fixedTime"
              format="HH:mm"
              value-format="HH:mm"
              placeholder="选择时间"
            />
          </el-form-item>
          <el-form-item label="星期几" v-if="showDayOfWeek">
            <el-select v-model="editForm.day_of_week" placeholder="选择星期">
              <el-option label="周一" :value="0" />
              <el-option label="周二" :value="1" />
              <el-option label="周三" :value="2" />
              <el-option label="周四" :value="3" />
              <el-option label="周五" :value="4" />
              <el-option label="周六" :value="5" />
              <el-option label="周日" :value="6" />
            </el-select>
          </el-form-item>
        </template>

        <el-form-item label="启用状态">
          <el-switch v-model="editForm.is_active" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSaveConfig">
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { request } from '@/api'
import dayjs from 'dayjs'

// ==================== 运行时任务 ====================
interface Job {
  id: string
  name: string
  func: string
  trigger: string
  next_run_time: string | null
  status: string
}

const loading = ref(false)
const jobs = ref<Job[]>([])
const triggeringId = ref<string | null>(null)

// ==================== 任务配置 ====================
interface TaskConfig {
  id: number
  task_name: string
  task_type: string
  hour: number | null
  minute: number | null
  day_of_week: number | null
  interval_minutes: number | null
  is_active: boolean
  config_version: number
  next_run: string | null
  created_at: string
}

const configsLoading = ref(false)
const configs = ref<TaskConfig[]>([])

// ==================== 编辑对话框 ====================
const editDialogVisible = ref(false)
const currentConfig = ref<TaskConfig | null>(null)
const saving = ref(false)
const editForm = reactive({
  task_type: 'interval',
  interval_minutes: 30,
  fixedTime: '00:00',
  day_of_week: null as number | null,
  is_active: true,
})

// ==================== 任务模式约束 ====================
// 从 constants 导入
import {
  INTERVAL_ONLY_TASKS,
  FIXED_ONLY_TASKS,
  WEEKLY_TASKS,
  isIntervalOnlyTask,
  isFixedOnlyTask,
  isWeeklyTask,
  getAllowedTaskTypes,
  getTaskMinInterval,
  FETCH_AI_NEWS_MIN_INTERVAL,
} from '@/constants/scheduler'
import type { ScheduledJob } from '@/types/api'

// 计算属性：当前任务是否强制 interval 模式
const isIntervalForced = computed(() => {
  return currentConfig.value && isIntervalOnlyTask(currentConfig.value.task_name)
})

// 计算属性：当前任务是否强制 fixed 模式
const isFixedForced = computed(() => {
  return currentConfig.value && isFixedOnlyTask(currentConfig.value.task_name)
})

// 计算属性：显示星期选择
const showDayOfWeek = computed(() => {
  return currentConfig.value && isWeeklyTask(currentConfig.value.task_name)
})

// 计算属性：间隔触发的最小值
const intervalMin = computed(() => {
  if (!currentConfig.value) return 1
  return getTaskMinInterval(currentConfig.value.task_name)
})

// 计算属性：间隔触发的最大值
const intervalMax = computed(() => {
  if (!currentConfig.value) return 1440
  if (currentConfig.value.task_name === 'process_pending_content') {
    const fetchConfig = configs.value.find(c => c.task_name === 'fetch_ai_news')
    if (fetchConfig && fetchConfig.task_type === 'interval') {
      const maxVal = (fetchConfig.interval_minutes || FETCH_AI_NEWS_MIN_INTERVAL) - 10
      return maxVal > 0 ? maxVal : 1
    }
    return 1440
  }
  return 1440
})

// 计算属性：间隔约束提示
const intervalConstraint = computed(() => {
  if (!currentConfig.value || editForm.task_type !== 'interval') return null

  const taskName = currentConfig.value.task_name

  if (taskName === 'process_pending_content') {
    const fetchConfig = configs.value.find(c => c.task_name === 'fetch_ai_news')
    if (fetchConfig && fetchConfig.task_type === 'interval') {
      const maxInterval = (fetchConfig.interval_minutes || FETCH_AI_NEWS_MIN_INTERVAL) - 10
      if (maxInterval <= 0) {
        return '资讯采集间隔太小，无法设置有效的处理间隔'
      }
      return `提示：需要比资讯采集小10分钟，最大可设置 ${maxInterval} 分钟`
    }
  }

  if (taskName === 'fetch_ai_news') {
    return '提示：最小间隔为 20 分钟'
  }

  return null
})

// ==================== 方法 ====================

function formatDate(date: string | null) {
  return date ? dayjs(date).format('YYYY-MM-DD HH:mm:ss') : '-'
}

// 定时任务状态卡片中的触发方式格式化 - 与任务配置卡片保持一致
function formatTrigger(trigger: string): string {
  if (!trigger) return '未知'

  // 解析参数辅助函数
  function getParam(key: string): string | null {
    const match = trigger.match(new RegExp(`${key}=([^,\\]]+)`))
    return match ? match[1].replace(/'/g, '') : null
  }

  // Cron 触发器
  if (trigger.startsWith('cron')) {
    const hour = getParam('hour')
    const minute = getParam('minute')
    const dayOfWeek = getParam('day_of_week')

    // 有星期参数 - 每周特定日期执行
    if (dayOfWeek && dayOfWeek !== '*') {
      const dayNames: Record<string, string> = {
        '0': '周一', '1': '周二', '2': '周三', '3': '周四',
        '4': '周五', '5': '周六', '6': '周日',
        'mon': '周一', 'tue': '周二', 'wed': '周三', 'thu': '周四',
        'fri': '周五', 'sat': '周六', 'sun': '周日',
      }
      const dayName = dayNames[dayOfWeek] || dayOfWeek
      const time = hour && minute
        ? `${hour.padStart(2, '0')}:${minute.padStart(2, '0')}`
        : '00:00'
      return `每周${dayName} ${time}`
    }

    // 无星期参数 - 每天固定时间执行
    if (hour !== null && minute !== null) {
      const time = `${hour.padStart(2, '0')}:${minute.padStart(2, '0')}`
      return `每天 ${time}`
    }

    return trigger
  }

  // Interval 触发器 - 格式如 interval[0:40:00] 表示 40分钟
  // APScheduler interval 格式: interval[days:hours:minutes:seconds]
  // 用户数据: interval[0:20:00] = 0天 20小时 00分? 但实际是 20分钟
  // 所以实际格式可能是 [hours:minutes:seconds]
  if (trigger.startsWith('interval')) {
    // 匹配 3 字段格式: [hours:minutes:seconds] 如 interval[0:20:00]
    const match3 = trigger.match(/interval\[(\d+):(\d+):(\d+)\]/)
    if (match3) {
      const hours = parseInt(match3[1])
      const minutes = parseInt(match3[2])

      if (hours > 0) {
        if (minutes > 0) {
          return `每 ${hours} 小时 ${minutes} 分钟`
        }
        return `每 ${hours} 小时`
      }
      return `每 ${minutes} 分钟`
    }

    // 匹配 4 字段格式: [days:hours:minutes:seconds]
    const match4 = trigger.match(/interval\[(\d+):(\d+):(\d+):(\d+)\]/)
    if (match4) {
      const days = parseInt(match4[1])
      const hours = parseInt(match4[2])
      const minutes = parseInt(match4[3])

      if (days > 0) return `每 ${days} 天`
      if (hours > 0) {
        if (minutes > 0) {
          return `每 ${hours} 小时 ${minutes} 分钟`
        }
        return `每 ${hours} 小时`
      }
      return `每 ${minutes} 分钟`
    }

    // 回退：尝试匹配其他格式
    const minutesMatch = getParam('minutes')
    const hoursMatch = getParam('hours')
    const daysMatch = getParam('days')

    if (daysMatch) return `每 ${daysMatch} 天`
    if (hoursMatch) return `每 ${hoursMatch} 小时`
    if (minutesMatch) return `每 ${minutesMatch} 分钟`
  }

  return trigger
}

function formatFixedTime(config: TaskConfig): string {
  if (config.hour === null || config.minute === null) return '-'
  const time = `${config.hour.toString().padStart(2, '0')}:${config.minute.toString().padStart(2, '0')}`
  if (config.day_of_week !== null) {
    const dayNames = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    return `每周${dayNames[config.day_of_week]} ${time}`
  }
  return `每天 ${time}`
}

async function fetchJobs() {
  loading.value = true
  try {
    const data = await request.get('/scheduler/jobs')
    jobs.value = data.items || []
  } catch (error) {
    console.error('获取任务列表失败:', error)
  } finally {
    loading.value = false
  }
}

async function handleTrigger(row: Job) {
  triggeringId.value = row.id
  try {
    await request.post(`/scheduler/jobs/${row.id}/trigger`)
    ElMessage.success('任务已触发')
    fetchJobs()
  } catch (error: any) {
    ElMessage.error(error.message || '触发失败')
  } finally {
    triggeringId.value = null
  }
}

async function fetchConfigs() {
  configsLoading.value = true
  try {
    const data = await request.get('/scheduler/configs', {
      params: { page: 1, page_size: 100 }
    })
    configs.value = data.items || []
  } catch (error) {
    console.error('获取配置列表失败:', error)
  } finally {
    configsLoading.value = false
  }
}

function openEditDialog(config: TaskConfig) {
  currentConfig.value = config
  editForm.task_type = config.task_type
  editForm.interval_minutes = config.interval_minutes || 30
  editForm.fixedTime = config.hour !== null && config.minute !== null
    ? `${config.hour.toString().padStart(2, '0')}:${config.minute.toString().padStart(2, '0')}`
    : '00:00'
  editForm.day_of_week = config.day_of_week
  editForm.is_active = config.is_active
  editDialogVisible.value = true
}

async function handleSaveConfig() {
  if (!currentConfig.value) return

  // 前端校验：如果任务是 interval-only，不能保存为 fixed
  if (isIntervalForced.value && editForm.task_type === 'fixed') {
    ElMessage.error('此任务只能使用间隔触发模式')
    return
  }

  // 前端校验：如果任务是 fixed-only，不能保存为 interval
  if (isFixedForced.value && editForm.task_type === 'interval') {
    ElMessage.error('此任务只能使用固定时间触发模式')
    return
  }

  saving.value = true
  try {
    const payload: any = {
      task_type: editForm.task_type,
      is_active: editForm.is_active,
    }

    if (editForm.task_type === 'interval') {
      payload.interval_minutes = editForm.interval_minutes
    } else {
      const [hour, minute] = editForm.fixedTime.split(':').map(Number)
      payload.hour = hour
      payload.minute = minute
      payload.day_of_week = editForm.day_of_week
    }

    await request.put(`/scheduler/configs/${currentConfig.value.id}`, payload)
    ElMessage.success('配置已保存')
    editDialogVisible.value = false
    fetchConfigs()
    fetchJobs()
  } catch (error: any) {
    ElMessage.error(error.message || '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  fetchJobs()
  fetchConfigs()
})
</script>

<style scoped>
.scheduler-page {
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

.jobs-card,
.configs-card {
  margin-bottom: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.cell-text {
  word-break: break-word;
  white-space: normal;
  line-height: 1.5;
}

.form-tip {
  margin-left: var(--spacing-sm);
  color: var(--color-text-muted);
  font-size: var(--font-size-small);
}

.constraint-alert {
  margin-top: var(--spacing-sm);
}
</style>
