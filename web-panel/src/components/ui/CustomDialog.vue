<template>
  <Teleport to="body">
    <Transition name="dialog-fade">
      <div v-if="modelValue" class="custom-dialog-overlay" @click.self="handleOverlayClick">
        <div
          class="custom-dialog-container"
          :class="[`dialog-size-${size}`, { 'is-fullscreen': fullscreen }]"
          role="dialog"
          :aria-modal="true"
        >
          <!-- Header -->
          <div class="dialog-header">
            <div class="dialog-title">
              <slot name="title">
                <span>{{ title }}</span>
              </slot>
            </div>
            <div class="dialog-header-actions">
              <button
                v-if="showFullscreen"
                class="header-btn"
                @click="toggleFullscreen"
                :title="fullscreen ? '退出全屏' : '全屏'"
              >
                <svg v-if="!fullscreen" viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
                  <path d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z"/>
                </svg>
                <svg v-else viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
                  <path d="M5 16h3v3h2v-5H5v2zm3-8H5v2h5V5H8v3zm6 11h2v-3h3v-2h-5v5zm2-11V5h-2v5h5V8h-3z"/>
                </svg>
              </button>
              <button class="header-btn header-btn-close" @click="handleClose" title="关闭">
                <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
                  <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                </svg>
              </button>
            </div>
          </div>

          <!-- Body -->
          <div class="dialog-body" :style="{ maxHeight: fullscreen ? 'calc(100vh - 120px)' : bodyMaxHeight }">
            <slot></slot>
          </div>

          <!-- Footer -->
          <div v-if="$slots.footer || showFooter" class="dialog-footer">
            <slot name="footer">
              <div class="footer-content">
                <slot name="footer-left"></slot>
                <slot name="footer-right"></slot>
              </div>
            </slot>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'

interface Props {
  modelValue: boolean
  title?: string
  size?: 'small' | 'medium' | 'large' | 'xlarge' | 'full'
  showFullscreen?: boolean
  closeOnClickOverlay?: boolean
  showFooter?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  title: '',
  size: 'xlarge',
  showFullscreen: true,
  closeOnClickOverlay: true,
  showFooter: true
})

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'close': []
}>()

const fullscreen = ref(false)

const bodyMaxHeight = computed(() => {
  const map: Record<string, string> = {
    small: '300px',
    medium: '400px',
    large: '500px',
    xlarge: 'calc(90vh - 180px)',
    full: 'calc(100vh - 120px)',
  }
  return map[props.size] || 'calc(90vh - 180px)'
})

function handleClose() {
  emit('update:modelValue', false)
  emit('close')
}

function handleOverlayClick() {
  if (props.closeOnClickOverlay) {
    handleClose()
  }
}

function toggleFullscreen() {
  fullscreen.value = !fullscreen.value
}

// Handle escape key
function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && props.modelValue) {
    handleClose()
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
})

// Prevent body scroll when dialog is open
watch(() => props.modelValue, (val) => {
  if (val) {
    document.body.style.overflow = 'hidden'
  } else {
    document.body.style.overflow = ''
  }
})
</script>

<style scoped>
/* Overlay */
.custom-dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  padding: 20px;
  box-sizing: border-box;
}

/* Container */
.custom-dialog-container {
  background: var(--el-bg-color, #fff);
  border-radius: 12px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 40px);
  overflow: hidden;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

/* Size variants */
.dialog-size-small {
  width: 500px;
  max-width: 95vw;
}

.dialog-size-medium {
  width: 700px;
  max-width: 95vw;
}

.dialog-size-large {
  width: 900px;
  max-width: 95vw;
}

.dialog-size-xlarge {
  width: 1200px;
  max-width: 95vw;
}

.dialog-size-full,
.is-fullscreen {
  width: calc(100vw - 40px);
  height: calc(100vh - 40px);
  max-width: none;
  max-height: none;
  border-radius: 8px;
}

/* Header */
.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--el-border-color, #ebeef5);
  background: var(--el-fill-color-light, #f5f7fa);
  flex-shrink: 0;
}

.dialog-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary, #303133);
}

.dialog-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  border-radius: 6px;
  cursor: pointer;
  color: var(--el-text-color-secondary, #909399);
  transition: all 0.2s;
}

.header-btn:hover {
  background: var(--el-fill-color, #e4e7ed);
  color: var(--el-text-color-primary, #303133);
}

.header-btn-close:hover {
  background: var(--el-color-danger-light, #fef0f0);
  color: var(--el-color-danger, #f56c6c);
}

/* Body */
.dialog-body {
  flex: 1;
  overflow: auto;
  padding: 0;
}

/* Footer */
.dialog-footer {
  padding: 16px 20px;
  border-top: 1px solid var(--el-border-color, #ebeef5);
  background: var(--el-fill-color-light, #f5f7fa);
  flex-shrink: 0;
}

.footer-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

/* Transition */
.dialog-fade-enter-active,
.dialog-fade-leave-active {
  transition: opacity 0.25s ease;
}

.dialog-fade-enter-active .custom-dialog-container,
.dialog-fade-leave-active .custom-dialog-container {
  transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.25s ease;
}

.dialog-fade-enter-from,
.dialog-fade-leave-to {
  opacity: 0;
}

.dialog-fade-enter-from .custom-dialog-container,
.dialog-fade-leave-to .custom-dialog-container {
  transform: scale(0.95) translateY(-20px);
  opacity: 0;
}

/* Responsive */
@media screen and (max-width: 768px) {
  .custom-dialog-overlay {
    padding: 0;
    align-items: flex-end;
  }

  .custom-dialog-container {
    width: 100% !important;
    max-width: 100% !important;
    border-radius: 16px 16px 0 0;
    max-height: 90vh;
    transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  }

  .is-fullscreen {
    height: 100vh !important;
    max-height: 100vh !important;
    border-radius: 0;
  }

  .dialog-fade-enter-from .custom-dialog-container,
  .dialog-fade-leave-to .custom-dialog-container {
    transform: translateY(100%);
  }
}
</style>
