<template>
  <div class="error-boundary">
    <slot />

    <!-- 错误提示 Toast -->
    <Transition name="error-toast">
      <div v-if="hasError && visible" class="error-toast">
        <div class="error-toast__icon">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <circle cx="10" cy="10" r="9" stroke="currentColor" stroke-width="2"/>
            <path d="M10 6v5M10 13.5v.5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
          </svg>
        </div>
        <div class="error-toast__content">
          <div class="error-toast__title">页面出现了一些问题</div>
          <div class="error-toast__message">{{ errorMessage }}</div>
        </div>
        <button class="error-toast__close" @click="handleClose">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M12 4L4 12M4 4l8 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
        </button>
      </div>
    </Transition>

    <!-- 错误详情弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      title="错误详情"
      width="500px"
      :close-on-click-overlay="false"
    >
      <div class="error-detail">
        <div class="error-detail__header">
          <el-icon size="48" color="var(--el-color-danger)"><WarnTriangleFilled /></el-icon>
          <h3>应用运行出错</h3>
        </div>
        <div class="error-detail__info">
          <p class="error-detail__message">{{ errorMessage }}</p>
          <p v-if="errorStack" class="error-detail__stack">{{ errorStack }}</p>
        </div>
        <div class="error-detail__actions">
          <el-button @click="handleReload">重新加载页面</el-button>
          <el-button type="primary" @click="handleDismiss">我知道了</el-button>
        </div>
      </div>
      <template #footer>
        <div class="error-detail__footer">
          <span class="error-detail__hint">如果问题持续存在，请刷新页面或联系管理员</span>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onErrorCaptured } from 'vue'
import { WarnTriangleFilled } from '@element-plus/icons-vue'

interface Props {
  /** 是否显示错误 Toast */
  showToast?: boolean
  /** 是否显示详细弹窗 */
  showDialog?: boolean
  /** 是否向上层传播错误 */
  propagate?: boolean
  /** 错误消退时间(ms)，0表示不自动消退 */
  duration?: number
}

const props = withDefaults(defineProps<Props>(), {
  showToast: true,
  showDialog: true,
  propagate: false,
  duration: 5000,
})

const emit = defineEmits<{
  /** 错误发生时触发 */
  error: [error: Error]
  /** 错误消散时触发 */
  dismissed: []
}>()

const hasError = ref(false)
const errorMessage = ref('')
const errorStack = ref('')
const visible = ref(true)
const dialogVisible = ref(false)

// 错误消亡计时器
let dismissTimer: ReturnType<typeof setTimeout> | null = null

/**
 * 捕获子组件错误
 */
onErrorCaptured((err: Error, instance, info) => {
  // 记录错误信息
  errorMessage.value = err.message || '未知错误'
  errorStack.value = err.stack || info

  hasError.value = true
  visible.value = true

  // 清除之前的计时器
  if (dismissTimer) {
    clearTimeout(dismissTimer)
    dismissTimer = null
  }

  // 设置自动消退计时器
  if (props.duration > 0) {
    dismissTimer = setTimeout(() => {
      handleDismiss()
    }, props.duration)
  }

  // 向上层传播
  if (props.propagate) {
    return true // 继续传播
  }
  return false // 阻止传播
})

/**
 * 关闭 Toast
 */
function handleClose() {
  if (dismissTimer) {
    clearTimeout(dismissTimer)
    dismissTimer = null
  }
  hasError.value = false
  visible.value = false
  emit('dismissed')
}

/**
 * 忽略错误，显示详情弹窗选项
 */
function handleDismiss() {
  if (dismissTimer) {
    clearTimeout(dismissTimer)
    dismissTimer = null
  }
  hasError.value = false
  visible.value = false
  emit('dismissed')
}

/**
 * 重新加载页面
 */
function handleReload() {
  window.location.reload()
}
</script>

<style scoped>
.error-boundary {
  position: relative;
}

/* Toast 样式 */
.error-toast {
  position: fixed;
  top: 80px;
  right: 20px;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  max-width: 380px;
  padding: 14px 16px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-color-danger);
  border-radius: var(--radius-lg);
  box-shadow:
    0 4px 12px rgba(239, 68, 68, 0.15),
    0 2px 4px rgba(0, 0, 0, 0.1);
  z-index: calc(var(--z-index-modal) + 10);
}

.error-toast__icon {
  flex-shrink: 0;
  color: var(--el-color-danger);
}

.error-toast__content {
  flex: 1;
  min-width: 0;
}

.error-toast__title {
  font-size: var(--font-size-small);
  font-weight: var(--font-weight-semibold);
  color: var(--el-text-color-primary);
  margin-bottom: 4px;
}

.error-toast__message {
  font-size: var(--font-size-small);
  color: var(--el-text-color-secondary);
  word-break: break-word;
}

.error-toast__close {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  padding: 0;
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  color: var(--el-text-color-secondary);
  cursor: pointer;
  transition: all var(--transition-duration-fast) var(--transition-timing);
}

.error-toast__close:hover {
  background: var(--el-fill-color);
  color: var(--el-text-color-primary);
}

/* Toast 动画 */
.error-toast-enter-active,
.error-toast-leave-active {
  transition: all 0.3s var(--transition-timing);
}

.error-toast-enter-from {
  opacity: 0;
  transform: translateX(20px);
}

.error-toast-leave-to {
  opacity: 0;
  transform: translateX(20px);
}

/* 错误详情弹窗样式 */
.error-detail {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.error-detail__header {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.error-detail__header h3 {
  font-size: var(--font-size-h4);
  font-weight: var(--font-weight-semibold);
  color: var(--el-text-color-primary);
  margin: 0;
}

.error-detail__info {
  width: 100%;
  text-align: left;
  background: var(--el-fill-color-light);
  border-radius: var(--radius-md);
  padding: 16px;
  margin-bottom: 20px;
}

.error-detail__message {
  font-size: var(--font-size-small);
  color: var(--el-text-color-primary);
  margin: 0 0 8px 0;
  word-break: break-word;
}

.error-detail__stack {
  font-size: 11px;
  font-family: var(--font-family-mono);
  color: var(--el-text-color-secondary);
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 150px;
  overflow-y: auto;
}

.error-detail__actions {
  display: flex;
  gap: 12px;
  justify-content: center;
}

.error-detail__footer {
  width: 100%;
  text-align: center;
}

.error-detail__hint {
  font-size: var(--font-size-small);
  color: var(--el-text-color-secondary);
}

/* 暗色模式适配 */
html.dark .error-toast {
  box-shadow:
    0 4px 12px rgba(239, 68, 68, 0.25),
    0 2px 4px rgba(0, 0, 0, 0.3);
}

html.dark .error-detail__info {
  background: var(--el-fill-color-dark);
}

/* 移动端适配 */
@media (max-width: 480px) {
  .error-toast {
    top: auto;
    bottom: 20px;
    right: 10px;
    left: 10px;
    max-width: none;
  }
}
</style>
