<template>
  <el-config-provider :locale="locale">
    <!-- 跳过导航链接 - 无障碍访问 -->
    <a href="#main-content" class="skip-link">跳转到主要内容</a>

    <!-- 全局错误边界 -->
    <ErrorBoundary>
      <!-- 网络状态指示器 -->
      <NetworkStatusIndicator />

      <router-view v-slot="{ Component }">
        <transition name="page-fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </ErrorBoundary>
  </el-config-provider>
</template>

<script setup lang="ts">
import { useTheme } from '@/composables/useTheme'
import { useRouter } from 'vue-router'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import ErrorBoundary from '@/components/ErrorBoundary.vue'
import NetworkStatusIndicator from '@/components/NetworkStatusIndicator.vue'

// Element Plus 中文语言包
const locale = zhCn

// 初始化主题 - 在应用启动时应用保存的主题
const { theme } = useTheme()

// 页面切换时滚动到顶部
const router = useRouter()
router.afterEach(() => {
  // 延迟执行确保DOM已更新
  setTimeout(() => {
    window.scrollTo({ top: 0, behavior: 'instant' as ScrollBehavior })
  }, 50)
})
</script>

<style>
#app {
  font-family: var(--font-family-ui);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* ==================== 跳过链接 - 无障碍访问 ==================== */

.skip-link {
  position: absolute;
  top: -100px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--color-primary);
  color: var(--color-text-inverse);
  padding: var(--spacing-sm) var(--spacing-md);
  border-radius: var(--radius-md);
  z-index: 9999;
  text-decoration: none;
  font-weight: var(--font-weight-medium);
  transition: top 0.2s ease;
}

.skip-link:focus {
  top: 10px;
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

/* ==================== 全局焦点样式 ==================== */

/* 键盘焦点指示器 - 更明显的焦点环 */
:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

/* 移除点击时的默认焦点环（仅保留键盘焦点） */
:focus:not(:focus-visible) {
  outline: none;
}

/* ==================== 页面切换过渡动画 ==================== */

.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.page-fade-enter-from {
  opacity: 0;
  transform: translateY(8px);
}

.page-fade-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
