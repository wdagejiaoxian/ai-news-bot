<template>
  <Teleport to="body">
    <Transition name="network-banner">
      <div v-if="showBanner" class="network-banner" :class="bannerClass">
        <div class="network-banner__content">
          <div class="network-banner__icon">
            <!-- 离线图标 -->
            <svg v-if="isOffline" width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path d="M2.5 10a7.5 7.5 0 0 1 13.54-3.54M17.5 10A7.5 7.5 0 0 1 4 16.5M5 5l10 10M15 5L5 15" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
            <!-- 重连中图标 -->
            <svg v-else-if="isReconnecting" width="20" height="20" viewBox="0 0 20 20" fill="none" class="spin">
              <circle cx="10" cy="10" r="8" stroke="currentColor" stroke-width="2" stroke-dasharray="50" stroke-dashoffset="20" stroke-linecap="round"/>
            </svg>
            <!-- 在线图标 -->
            <svg v-else width="20" height="20" viewBox="0 0 20 20" fill="none">
              <circle cx="10" cy="10" r="8" stroke="currentColor" stroke-width="1.5"/>
              <path d="M6.5 10l2.5 2.5 4-5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </div>
          <div class="network-banner__text">
            <span v-if="isOffline" class="network-banner__title">网络连接已断开</span>
            <span v-else-if="isReconnecting" class="network-banner__title">正在重新连接...</span>
            <span v-else class="network-banner__title">网络已恢复</span>
            <span v-if="isOffline" class="network-banner__desc">请检查您的网络设置</span>
          </div>
        </div>
        <div class="network-banner__actions">
          <el-button
            v-if="isOffline"
            size="small"
            type="primary"
            :loading="isRetrying"
            @click="handleRetry"
          >
            重试
          </el-button>
          <el-button
            v-else-if="isReconnecting"
            size="small"
            @click="handleDismiss"
          >
            取消
          </el-button>
          <el-button
            v-else
            size="small"
            @click="handleDismiss"
          >
            知道了
          </el-button>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useNetworkStatus } from '@/composables/useNetworkStatus'

interface Props {
  /** 是否显示网络状态横幅 */
  enabled?: boolean
  /** 离线时自动显示 */
  autoShowOnOffline?: boolean
  /** 在线恢复后自动消失延迟(ms) */
  autoHideDelay?: number
}

const props = withDefaults(defineProps<Props>(), {
  enabled: true,
  autoShowOnOffline: true,
  autoHideDelay: 3000,
})

const { isOnline, isOffline, retry: doRetry } = useNetworkStatus()

const isRetrying = ref(false)
const isReconnecting = ref(false)
const showBanner = ref(false)
const bannerType = ref<'offline' | 'online' | 'reconnecting'>('offline')

// 横幅样式类
const bannerClass = computed(() => {
  return {
    'network-banner--offline': bannerType.value === 'offline',
    'network-banner--online': bannerType.value === 'online',
    'network-banner--reconnecting': bannerType.value === 'reconnecting',
  }
})

// 监听离线状态变化
watch(isOffline, (offline) => {
  if (offline && props.autoShowOnOffline) {
    bannerType.value = 'offline'
    showBanner.value = true
    isReconnecting.value = false
  }
})

// 监听在线状态变化
watch(isOnline, (online) => {
  if (online && showBanner.value) {
    bannerType.value = 'online'
    isReconnecting.value = false

    // 延迟隐藏
    if (props.autoHideDelay > 0) {
      setTimeout(() => {
        showBanner.value = false
      }, props.autoHideDelay)
    }
  }
})

/**
 * 处理重试按钮点击
 */
async function handleRetry() {
  isRetrying.value = true
  isReconnecting.value = true
  bannerType.value = 'reconnecting'

  try {
    const success = await doRetry()
    if (success) {
      bannerType.value = 'online'
      if (props.autoHideDelay > 0) {
        setTimeout(() => {
          showBanner.value = false
        }, props.autoHideDelay)
      }
    } else {
      bannerType.value = 'offline'
    }
  } catch {
    bannerType.value = 'offline'
  } finally {
    isRetrying.value = false
    isReconnecting.value = false
  }
}

/**
 * 关闭横幅
 */
function handleDismiss() {
  showBanner.value = false
}
</script>

<style scoped>
/* 横幅容器 */
.network-banner {
  position: fixed;
  top: 80px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 20px;
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-lg);
  z-index: calc(var(--z-index-tooltip) + 10);
  max-width: calc(100vw - 40px);
}

.network-banner--offline {
  background: var(--el-color-danger);
  color: var(--el-color-white);
}

.network-banner--online {
  background: var(--el-color-success);
  color: var(--el-color-white);
}

.network-banner--reconnecting {
  background: var(--el-color-warning);
  color: var(--el-color-white);
}

/* 内容区域 */
.network-banner__content {
  display: flex;
  align-items: center;
  gap: 12px;
}

.network-banner__icon {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.network-banner__text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.network-banner__title {
  font-size: var(--font-size-small);
  font-weight: var(--font-weight-semibold);
}

.network-banner__desc {
  font-size: 12px;
  opacity: 0.8;
}

/* 操作按钮 */
.network-banner__actions {
  flex-shrink: 0;
}

/* 旋转动画 */
.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 过渡动画 */
.network-banner-enter-active,
.network-banner-leave-active {
  transition: all 0.3s var(--transition-timing);
}

.network-banner-enter-from,
.network-banner-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(-20px);
}

/* 暗色模式适配 */
html.dark .network-banner--offline {
  background: var(--el-color-danger);
}

html.dark .network-banner--online {
  background: var(--el-color-success);
}

/* 移动端适配 */
@media (max-width: 480px) {
  .network-banner {
    top: auto;
    bottom: 20px;
    left: 10px;
    right: 10px;
    transform: none;
    flex-direction: column;
    text-align: center;
    padding: 16px;
  }

  .network-banner__content {
    flex-direction: column;
    gap: 8px;
  }

  .network-banner-enter-from,
  .network-banner-leave-to {
    transform: translateY(20px);
  }
}
</style>
