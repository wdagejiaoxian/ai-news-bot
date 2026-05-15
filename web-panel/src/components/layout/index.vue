<template>
  <el-container class="layout-container">
    <!-- 网络状态指示器 -->
    <NetworkStatusIndicator />

    <!-- 移动端遮罩层 -->
    <Transition name="fade">
      <div
        v-if="isMobile && sidebarVisible"
        class="sidebar-overlay"
        @click="sidebarVisible = false"
        @touchstart="handleOverlayTouchStart"
        @touchmove="handleOverlayTouchMove"
        @touchend="handleOverlayTouchEnd"
      />
    </Transition>

    <!-- 移动端边缘滑动检测层（始终存在，仅在移动端激活） -->
    <div
      v-if="isMobile"
      class="edge-swipe-detector"
      @touchstart="handleEdgeSwipeStart"
      @touchmove="handleEdgeSwipeMove"
      @touchend="handleEdgeSwipeEnd"
    />

    <!-- 侧边栏 -->
    <aside
      :width="isMobile ? '260px' : (sidebarCollapsed ? sidebarCollapsedWidth : sidebarWidth)"
      class="sidebar"
      :class="{
        'sidebar--collapsed': sidebarCollapsed && !isMobile,
        'sidebar--mobile-hidden': isMobile && !sidebarVisible
      }"
    >
      <!-- Logo区域 -->
      <div class="sidebar-header">
        <!-- 桌面端展开/收起按钮 - 放在Logo左侧 -->
        <el-tooltip
          v-if="!isMobile"
          :content="sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'"
          placement="right"
        >
          <div class="sidebar-header-toggle" @click="toggleSidebar">
            <el-icon :size="18">
              <component :is="sidebarCollapsed ? Expand : Fold" />
            </el-icon>
          </div>
        </el-tooltip>

        <div class="logo">
          <div class="logo-icon">
            <el-icon :size="24"><DataBoard /></el-icon>
          </div>
          <Transition name="fade-slide">
            <span v-if="!(sidebarCollapsed && !isMobile)" class="logo-text">
              AI News Bot
            </span>
          </Transition>
        </div>
      </div>

      <!-- 主导航 -->
      <nav class="sidebar-nav">
        <div class="nav-section">
          <Transition name="fade-slide">
            <span v-if="!(sidebarCollapsed && !isMobile)" class="nav-label">主要功能</span>
          </Transition>
          <template v-for="item in mainNavItems" :key="item.path">
            <el-tooltip
              v-if="sidebarCollapsed && !isMobile"
              :content="item.label"
              placement="right"
              :show-after="200"
            >
              <router-link
                :to="item.path"
                class="nav-item"
                :class="{ 'nav-item--active': activeMenu === item.path }"
              >
                <div class="nav-item__icon">
                  <el-icon :size="20"><component :is="item.icon" /></el-icon>
                </div>
                <div v-if="!(sidebarCollapsed && !isMobile)" class="nav-item__indicator" />
              </router-link>
            </el-tooltip>
            <router-link
              v-else
              :to="item.path"
              class="nav-item"
              :class="{ 'nav-item--active': activeMenu === item.path }"
            >
              <div class="nav-item__icon">
                <el-icon :size="20"><component :is="item.icon" /></el-icon>
              </div>
              <Transition name="fade-slide">
                <span class="nav-item__text">
                  {{ item.label }}
                </span>
              </Transition>
              <Transition name="fade-slide">
                <div class="nav-item__indicator" />
              </Transition>
            </router-link>
          </template>
        </div>

        <div class="nav-section">
          <Transition name="fade-slide">
            <span v-if="!(sidebarCollapsed && !isMobile)" class="nav-label">系统</span>
          </Transition>
          <template v-for="item in systemNavItems" :key="item.path">
            <el-tooltip
              v-if="sidebarCollapsed && !isMobile"
              :content="item.label"
              placement="right"
              :show-after="200"
            >
              <router-link
                :to="item.path"
                class="nav-item"
                :class="{ 'nav-item--active': activeMenu === item.path }"
              >
                <div class="nav-item__icon">
                  <el-icon :size="20"><component :is="item.icon" /></el-icon>
                </div>
                <div v-if="!(sidebarCollapsed && !isMobile)" class="nav-item__indicator" />
              </router-link>
            </el-tooltip>
            <router-link
              v-else
              :to="item.path"
              class="nav-item"
              :class="{ 'nav-item--active': activeMenu === item.path }"
            >
              <div class="nav-item__icon">
                <el-icon :size="20"><component :is="item.icon" /></el-icon>
              </div>
              <Transition name="fade-slide">
                <span class="nav-item__text">
                  {{ item.label }}
                </span>
              </Transition>
              <Transition name="fade-slide">
                <div class="nav-item__indicator" />
              </Transition>
            </router-link>
          </template>
        </div>
      </nav>

      <!-- 底部用户区域 -->
      <div class="sidebar-footer" ref="footerRef">
        <!-- 自定义用户下拉框 -->
        <div class="user-menu">
          <div
            class="user-menu__trigger"
            :class="{ 'is-active': menuVisible }"
            @click="menuVisible = !menuVisible"
          >
            <div class="user-avatar">
              <span class="user-avatar__letter">
                {{ userInfo?.username?.charAt(0)?.toUpperCase() || 'U' }}
              </span>
            </div>
            <div class="user-info">
              <span class="user-info__name">{{ userInfo?.username || '用户' }}</span>
              <span class="user-info__role">{{ userInfo?.role === 'admin' ? '管理员' : '普通用户' }}</span>
            </div>
            <div class="user-menu__arrow" :class="{ 'is-open': menuVisible }">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </div>
          </div>

          <!-- 下拉菜单 -->
          <Transition name="menu-fade">
            <div v-if="menuVisible" class="user-menu__dropdown">
              <div class="user-menu__item" @click="handleSettings">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <path d="M8 10C9.10457 10 10 9.10457 10 8C10 6.89543 9.10457 6 8 6C6.89543 6 6 6.89543 6 8C6 9.10457 6.89543 10 8 10Z" stroke="currentColor" stroke-width="1.5"/>
                  <path d="M13.5 8C13.5 8.53 13.46 9.05 13.38 9.55L14.77 10.59C14.92 10.71 14.96 10.92 14.86 11.09L13.12 14.09C13.02 14.26 12.81 14.32 12.62 14.24L11.26 13.61C10.59 14.05 9.82 14.36 9 14.5L8.77 15.86C8.73 16.05 8.56 16.18 8.37 16.18H5.63C5.44 16.18 5.27 16.05 5.23 15.86L5 14.5C4.18 14.36 3.41 14.05 2.74 13.61L1.38 14.24C1.19 14.32 0.98 14.26 0.88 14.09L0.14 11.09C0.04 10.92 0.08 10.71 0.23 10.59L1.62 9.55C1.54 9.05 1.5 8.53 1.5 8C1.5 7.47 1.54 6.95 1.62 6.45L0.23 5.41C0.08 5.29 0.04 5.08 0.14 4.91L0.88 1.91C0.98 1.74 1.19 1.68 1.38 1.76L2.74 2.39C3.41 1.95 4.18 1.64 5 1.5L5.23 0.14C5.27 -0.05 5.44 -0.18 5.63 -0.18H8.37C8.56 -0.18 8.73 -0.05 8.77 0.14L9 1.5C9.82 1.64 10.59 1.95 11.26 2.39L12.62 1.76C12.81 1.68 13.02 1.74 13.12 1.91L13.86 4.91C13.96 5.08 13.92 5.29 13.77 5.41L12.38 6.45C12.46 6.95 12.5 7.47 12.5 8H13.5Z" stroke="currentColor" stroke-width="1.5"/>
                </svg>
                <span>设置</span>
              </div>
              <div class="user-menu__divider"></div>
              <div class="user-menu__item user-menu__item--danger" @click="handleLogout">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <path d="M6 14H3.33333C2.97971 14 2.64057 13.8595 2.39052 13.6095C2.14048 13.3594 2 13.0203 2 12.6667V3.33333C2 2.97971 2.14048 2.64057 2.39052 2.39052C2.64057 2.14048 2.97971 2 3.33333 2H6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                  <path d="M10.6667 11.3333L14 8L10.6667 4.66667" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                  <path d="M14 8H6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                <span>退出登录</span>
              </div>
            </div>
          </Transition>
        </div>
      </div>
    </aside>

    <el-container class="main-container">
      <!-- 顶部导航 -->
      <header class="header">
        <div class="header-left">
          <!-- 移动端汉堡菜单 -->
          <el-button
            v-if="isMobile"
            text
            class="menu-btn"
            @click="sidebarVisible = true"
          >
            <el-icon :size="22"><Menu /></el-icon>
          </el-button>

          <!-- 面包屑 -->
          <nav class="breadcrumb">
            <el-breadcrumb separator="/">
              <el-breadcrumb-item :to="{ path: '/' }">
                <span class="breadcrumb-home">
                  <el-icon :size="14"><House /></el-icon>
                  首页
                </span>
              </el-breadcrumb-item>
              <el-breadcrumb-item v-if="route.meta.title">
                {{ route.meta.title }}
              </el-breadcrumb-item>
            </el-breadcrumb>
          </nav>
        </div>

        <div class="header-right">
          <!-- 主题切换 -->
          <div class="theme-toggle" @click="toggleTheme">
            <div class="theme-toggle__track" :class="{ 'theme-toggle__track--dark': isDark }">
              <div class="theme-toggle__thumb">
                <el-icon :size="12">
                  <Moon v-if="isDark" />
                  <Sunny v-else />
                </el-icon>
              </div>
            </div>
          </div>
        </div>
      </header>

      <!-- 主内容区 -->
      <main class="main-content">
        <ErrorBoundary>
          <router-view v-slot="{ Component }">
            <transition name="page-fade" mode="out-in">
              <component :is="Component" />
            </transition>
          </router-view>
        </ErrorBoundary>
      </main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted, markRaw } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { ElMessage } from 'element-plus'
import {
  DataBoard,
  Document,
  Connection,
  Cpu,
  Bell,
  Star,
  Timer,
  DocumentCopy,
  Fold,
  Expand,
  Menu,
  Moon,
  Sunny,
  House,
  User,
  QuestionFilled,
  TrendCharts,
} from '@element-plus/icons-vue'
import { useAppStore, useUserStore } from '@/store'
import { useTheme, useResponsive } from '@/composables/useTheme'
import NetworkStatusIndicator from '@/components/NetworkStatusIndicator.vue'
import ErrorBoundary from '@/components/ErrorBoundary.vue'

const route = useRoute()
const router = useRouter()
const appStore = useAppStore()
const userStore = useUserStore()
const { theme, isDark, toggleTheme } = useTheme()
const { breakpoint, isMobile } = useResponsive()

const { sidebarCollapsed } = storeToRefs(appStore)
const { userInfo } = storeToRefs(userStore)

// 布局常量
const sidebarWidth = '260px'
const sidebarCollapsedWidth = '72px'

// 移动端侧边栏可见性
const sidebarVisible = ref(false)

// 菜单配置
const mainNavItems = [
  { path: '/dashboard', label: '数据看板', icon: markRaw(DataBoard) },
  { path: '/articles', label: '文章管理', icon: markRaw(Document) },
  { path: '/rss', label: 'RSS源管理', icon: markRaw(Connection) },
  { path: '/rsshub-help', label: 'RSSHub 帮助', icon: markRaw(QuestionFilled) },
  { path: '/user-llm-config', label: '我的LLM', icon: markRaw(Cpu) },
  { path: '/clusters', label: '主题聚类', icon: markRaw(TrendCharts) },
  { path: '/vector/models', label: 'Embedding模型', icon: markRaw(Connection) },
  { path: '/vector/db', label: '向量库配置', icon: markRaw(Connection) },
  { path: '/webhook-config', label: 'Webhook', icon: markRaw(Bell) },
  { path: '/github', label: 'GitHub项目', icon: markRaw(Star) },
]

const systemNavItems = [
  { path: '/scheduler', label: '定时任务', icon: markRaw(Timer) },
  { path: '/logs', label: '操作日志', icon: markRaw(DocumentCopy) },
]

const activeMenu = computed(() => route.path)

// 用户菜单状态
const menuVisible = ref(false)
const footerRef = ref<HTMLElement | null>(null)

function toggleSidebar(): void {
  // 移动端：切换 sidebarVisible；桌面端：切换 sidebarCollapsed
  if (isMobile.value) {
    sidebarVisible.value = false
  } else {
    appStore.toggleSidebar()
  }
}

function handleSettings(): void {
  menuVisible.value = false
  router.push('/settings')
}

function handleLogout(): void {
  menuVisible.value = false
  userStore.logout()
  router.push('/login')
  ElMessage.success('已退出登录')
}

// 点击外部关闭菜单
function handleClickOutside(e: MouseEvent): void {
  if (footerRef.value && !footerRef.value.contains(e.target as Node)) {
    menuVisible.value = false
  }
}

// 移动端检测
function handleResize(): void {
  if (window.innerWidth < 768 && !sidebarVisible.value) {
    // 移动端默认隐藏侧边栏
  }
}

// ==================== 移动端滑动手势 ====================

let touchStartX = 0
let touchStartY = 0
const SWIPE_THRESHOLD = 50 // 滑动的最小距离
const EDGE_SWIPE_ZONE = 15 // 屏幕边缘滑动区域百分比

// 标记是否正在监听边缘滑动（避免与 overlay 冲突）
let isEdgeSwipeActive = false

/**
 * 处理边缘滑动打开侧边栏
 * 从屏幕左边缘15%区域内开始触摸并向右滑动时，打开侧边栏
 */
function handleEdgeSwipeStart(e: TouchEvent): void {
  // 仅在移动端处理
  if (!isMobile.value) return

  const touchX = e.touches[0].clientX
  const screenWidth = window.innerWidth
  const edgeZone = screenWidth * (EDGE_SWIPE_ZONE / 100)

  // 如果触摸点在屏幕左边缘区域内
  if (touchX <= edgeZone) {
    isEdgeSwipeActive = true
    touchStartX = touchX
    touchStartY = e.touches[0].clientY
  }
}

function handleEdgeSwipeMove(e: TouchEvent): void {
  // 暂不支持滑动预览
}

function handleEdgeSwipeEnd(e: TouchEvent): void {
  if (!isEdgeSwipeActive) return

  const touchEndX = e.changedTouches[0].clientX
  const touchEndY = e.changedTouches[0].clientY
  const deltaX = touchEndX - touchStartX
  const deltaY = touchEndY - touchStartY

  // 重置状态
  isEdgeSwipeActive = false

  // 如果在左边缘区域开始触摸，向右滑动超过阈值，则打开侧边栏
  if (deltaX > SWIPE_THRESHOLD && Math.abs(deltaY) < Math.abs(deltaX)) {
    sidebarVisible.value = true
  }
}

function handleOverlayTouchStart(e: TouchEvent): void {
  // 如果是从遮罩层开始触摸，记录起点
  touchStartX = e.touches[0].clientX
  touchStartY = e.touches[0].clientY
}

function handleOverlayTouchMove(e: TouchEvent): void {
  // 可以添加滑动预览效果
}

function handleOverlayTouchEnd(e: TouchEvent): void {
  const touchEndX = e.changedTouches[0].clientX
  const touchEndY = e.changedTouches[0].clientY
  const deltaX = touchEndX - touchStartX
  const deltaY = touchEndY - touchStartY

  // 如果是从左向右滑动超过阈值，关闭侧边栏
  if (deltaX > SWIPE_THRESHOLD && Math.abs(deltaY) < Math.abs(deltaX)) {
    sidebarVisible.value = false
  }
}

onMounted(async () => {
  // 加载用户信息
  if (userStore.isLoggedIn && !userStore.userInfo) {
    try {
      await userStore.fetchUserInfo()
    } catch {
      // Token无效，路由守卫会处理
    }
  }

  // 添加窗口resize监听
  window.addEventListener('resize', handleResize)
  // 添加点击外部关闭菜单
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  document.removeEventListener('click', handleClickOutside)
})
</script>

<style scoped>
/* ==================== 布局容器 ==================== */

.layout-container {
  height: 100vh;
  overflow: hidden;
  background-color: var(--color-bg-content);
}

.main-container {
  flex-direction: column;
}

/* ==================== 侧边栏 ==================== */

.sidebar {
  width: var(--sidebar-width);
  background: linear-gradient(180deg, var(--color-bg-sidebar) 0%, var(--color-bg-sidebar) 100%);
  border-right: 1px solid var(--color-white-alpha-06);
  display: flex;
  flex-direction: column;
  transition: width var(--transition-duration-normal) var(--transition-timing),
              transform var(--transition-duration-normal) var(--transition-timing);
  overflow: hidden;
  z-index: var(--z-index-sidebar);
}

.sidebar--collapsed {
  width: var(--sidebar-collapsed-width);
}

.sidebar--mobile-hidden {
  transform: translateX(-100%);
}

@media (max-width: 767px) {
  .sidebar {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    width: 260px;
    z-index: var(--z-index-sidebar);
    box-shadow: 4px 0 20px var(--color-black-alpha-30);
    transition: transform var(--transition-duration-normal) var(--transition-timing);
  }

  .sidebar--mobile-hidden {
    transform: translateX(-100%);
    box-shadow: none;
  }
}

/* ==================== 平板断点（768px - 1024px） ==================== */
@media (min-width: 768px) and (max-width: 1024px) {
  .sidebar {
    width: 72px;
  }

  /* 侧边栏头部 - 居中显示 */
  .sidebar .sidebar-header {
    flex-direction: column;
    justify-content: center;
    align-items: center;
    padding: var(--spacing-sm);
    gap: var(--spacing-sm);
  }

  .sidebar .sidebar-header-toggle {
    margin: 0 auto;
    width: 28px;
    height: 28px;
  }

  /* Logo - 只显示图标 */
  .sidebar .logo {
    flex-direction: column;
    flex: 0 0 auto;
    gap: var(--spacing-xs);
  }

  .sidebar .logo-icon {
    width: 32px;
    height: 32px;
    margin: 0 auto;
  }

  .sidebar .logo-text {
    display: none;
  }

  /* 隐藏文字和指示器 */
  .sidebar .nav-label,
  .sidebar .nav-item__text,
  .sidebar .nav-item__indicator {
    display: none;
  }

  /* 导航项居中 */
  .sidebar .nav-item {
    justify-content: center;
    padding: var(--spacing-sm);
  }

  /* 用户菜单居中 */
  .sidebar .user-menu__trigger {
    justify-content: center;
    padding: 10px;
  }

  .sidebar .user-info,
  .sidebar .user-menu__arrow {
    display: none;
  }

  .sidebar .user-avatar {
    width: 32px;
    height: 32px;
  }

  .main-content {
    padding: var(--spacing-md);
  }

  .header {
    padding: 0 var(--spacing-md);
  }
}

/* ==================== Logo区域 ==================== */

.sidebar-header {
  padding: var(--spacing-md);
  border-bottom: 1px solid var(--color-white-alpha-06);
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

/* 侧边栏头部展开/收起按钮 */
.sidebar-header-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  cursor: pointer;
  color: var(--color-sidebar-text);
  opacity: 0.7;
  transition: all var(--transition-duration-fast) var(--transition-timing);
  flex-shrink: 0;
}

.sidebar-header-toggle:hover {
  opacity: 1;
  background-color: var(--color-white-alpha-06);
  color: var(--color-sidebar-text-hover);
}

/* 收起状态：保持toggle按钮可显示 */
.sidebar--collapsed .sidebar-header-toggle {
  margin: 0 auto;
}

/* 收起状态下的侧边栏头部布局 - 垂直排列，居中显示 */
.sidebar--collapsed .sidebar-header {
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-md) var(--spacing-sm);
  height: auto;
  min-height: 80px;
}

.logo {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  flex: 1;
  min-width: 0;
  justify-content: center;
}

/* 折叠状态下Logo图标缩小居中显示，隐藏文字 */
.sidebar--collapsed .logo {
  flex-direction: column;
  flex: 0 0 auto;
  width: 100%;
  gap: var(--spacing-md);
}

.sidebar--collapsed .logo-icon {
  margin: 0 auto;
  width: 36px;
  height: 36px;
  font-size: 18px;
}

.sidebar--collapsed .logo-text {
  display: none;
}

.logo-icon {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-lg);
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-hover) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-inverse);
  flex-shrink: 0;
  box-shadow: 0 4px 12px var(--color-primary-alpha-30);
}

.logo-text {
  font-family: var(--font-family-display);
  font-size: var(--font-size-body);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-inverse);
  white-space: nowrap;
  letter-spacing: -0.02em;
}

/* ==================== 导航区域 ==================== */

.sidebar-nav {
  flex: 1;
  padding: var(--spacing-sm) 0;
  overflow-y: auto;
  overflow-x: hidden;
}

/* 自定义滚动条样式 */
.sidebar-nav::-webkit-scrollbar {
  width: 4px;
}

.sidebar-nav::-webkit-scrollbar-track {
  background: transparent;
}

.sidebar-nav::-webkit-scrollbar-thumb {
  background: var(--color-primary-alpha-30);
  border-radius: 2px;
}

.sidebar-nav::-webkit-scrollbar-thumb:hover {
  background: var(--color-primary-alpha-50);
}

.nav-section {
  margin-bottom: var(--spacing-sm);
}

.nav-label {
  display: block;
  font-size: 10px;
  font-weight: var(--font-weight-semibold);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--color-sidebar-text);
  opacity: 0.4;
  margin-bottom: var(--spacing-xs);
  padding-left: var(--spacing-md);
  padding-right: var(--spacing-sm);
  white-space: nowrap;
  overflow: hidden;
}

.sidebar--collapsed .nav-label {
  opacity: 0;
  height: 0;
  margin: 0;
  padding: 0;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  border-radius: 0;
  color: var(--color-sidebar-text);
  text-decoration: none;
  cursor: pointer;
  position: relative;
  transition:
    background-color var(--transition-duration-normal) var(--transition-timing),
    color var(--transition-duration-normal) var(--transition-timing);
}

.sidebar--collapsed .nav-item {
  justify-content: center;
  padding: var(--spacing-sm);
}

.nav-item:hover {
  background-color: var(--color-white-alpha-06);
  color: var(--color-sidebar-text-hover);
}

.sidebar--collapsed .nav-item:hover {
  background-color: transparent;
}

.nav-item--active {
  background-color: var(--color-primary-alpha-10);
  color: var(--color-sidebar-text-active);
}

.nav-item--active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 24px;
  background: var(--color-primary);
  border-radius: 0 2px 2px 0;
}

.nav-item__icon {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: var(--color-white-alpha-06);
  transition:
    background-color var(--transition-duration-fast) var(--transition-timing),
    transform var(--transition-duration-fast) var(--transition-timing);
}

.nav-item:hover .nav-item__icon {
  background: var(--color-white-alpha-10);
}

.nav-item--active .nav-item__icon {
  background: var(--color-primary);
  color: var(--color-text-inverse);
}

.nav-item__text {
  flex: 1;
  font-size: var(--font-size-small);
  font-weight: var(--font-weight-medium);
  white-space: nowrap;
}

.sidebar--collapsed .nav-item__text {
  display: none;
}

.nav-item__indicator {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: var(--color-primary);
  opacity: 0;
  transition: opacity var(--transition-duration-fast) var(--transition-timing);
}

.nav-item--active .nav-item__indicator {
  opacity: 1;
}

.sidebar--collapsed .nav-item__indicator {
  display: none;
}

/* ==================== 侧边栏底部 ==================== */

.sidebar-footer {
  padding: var(--spacing-md);
  border-top: 1px solid var(--color-white-alpha-06);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.sidebar--collapsed .sidebar-footer {
  align-items: center;
}

/* ==================== 用户菜单 ==================== */

.user-menu {
  position: relative;
  width: 100%;
}

.user-menu__trigger {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: 10px 12px;
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: all var(--transition-duration-normal) var(--transition-timing);
  width: 100%;
  box-sizing: border-box;
  background: transparent;
  border: none;
  outline: none;
}

.user-menu__trigger:hover {
  background: var(--color-white-alpha-06);
}

.user-menu__trigger.is-active {
  background: var(--color-white-alpha-08);
}

.user-menu__trigger:active {
  transform: scale(0.98);
}

/* 用户头像 */
.user-avatar {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-hover) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 2px 8px var(--color-primary-alpha-30);
  transition: all var(--transition-duration-normal) var(--transition-timing);
}

.user-menu__trigger:hover .user-avatar {
  transform: scale(1.08);
  box-shadow: 0 4px 16px var(--color-primary-alpha-40);
}

.user-avatar__letter {
  color: var(--color-text-inverse);
  font-weight: var(--font-weight-semibold);
  font-size: var(--font-size-small);
  font-family: var(--font-family-display);
}

/* 用户信息 */
.user-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  text-align: left;
}

.user-info__name {
  font-size: var(--font-size-small);
  font-weight: var(--font-weight-semibold);
  color: var(--color-sidebar-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  letter-spacing: 0.01em;
  transition: color var(--transition-duration-fast) var(--transition-timing);
}

.user-menu__trigger:hover .user-info__name {
  color: var(--color-sidebar-text-hover);
}

.user-info__role {
  font-size: 11px;
  color: var(--color-sidebar-text);
  opacity: 0.6;
  white-space: nowrap;
  font-weight: var(--font-weight-medium);
  letter-spacing: 0.02em;
  transition: opacity var(--transition-duration-fast) var(--transition-timing);
}

.user-menu__trigger:hover .user-info__role {
  opacity: 0.8;
}

/* 下拉箭头 */
.user-menu__arrow {
  color: var(--color-sidebar-text);
  opacity: 0.5;
  flex-shrink: 0;
  transition: all var(--transition-duration-normal) var(--transition-timing);
  display: flex;
  align-items: center;
  justify-content: center;
}

.user-menu__trigger:hover .user-menu__arrow {
  opacity: 0.8;
}

.user-menu__arrow.is-open {
  transform: rotate(180deg);
  opacity: 1;
}

/* 折叠状态下隐藏文字 */
.sidebar--collapsed .user-info {
  display: none;
}

.sidebar--collapsed .user-menu__arrow {
  display: none;
}

.sidebar--collapsed .user-menu__trigger {
  justify-content: center;
  padding: 12px;
}

/* ==================== 下拉菜单 ==================== */

.user-menu__dropdown {
  position: absolute;
  bottom: calc(100% + 8px);
  left: 0;
  right: 0;
  min-width: 200px;
  background: var(--color-bg-sidebar);
  border: 1px solid var(--color-white-alpha-10);
  border-radius: var(--radius-xl);
  box-shadow:
    0 -4px 24px rgba(0, 0, 0, 0.3),
    0 2px 8px rgba(0, 0, 0, 0.2),
    inset 0 1px 0 var(--color-white-alpha-05);
  padding: 8px;
  z-index: var(--z-index-tooltip);
}

.user-menu__item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: var(--radius-md);
  font-size: var(--font-size-small);
  font-weight: var(--font-weight-medium);
  color: var(--color-sidebar-text);
  cursor: pointer;
  transition: all var(--transition-duration-fast) var(--transition-timing);
}

.user-menu__item:hover {
  background: var(--color-white-alpha-08);
  color: var(--color-sidebar-text-hover);
}

.user-menu__item:active {
  transform: scale(0.98);
}

.user-menu__item svg {
  flex-shrink: 0;
  opacity: 0.8;
  transition: opacity var(--transition-duration-fast) var(--transition-timing);
}

.user-menu__item:hover svg {
  opacity: 1;
}

.user-menu__divider {
  height: 1px;
  background: var(--color-white-alpha-08);
  margin: 6px 0;
}

.user-menu__item--danger {
  color: var(--color-danger);
}

.user-menu__item--danger:hover {
  background: var(--color-danger-alpha-10);
  color: var(--color-danger-hover);
}

/* 菜单动画 */
.menu-fade-enter-active,
.menu-fade-leave-active {
  transition: all 0.2s var(--transition-timing);
}

.menu-fade-enter-from,
.menu-fade-leave-to {
  opacity: 0;
  transform: translateY(8px) scale(0.96);
}

/* 暗色模式适配 */
html.dark .user-menu__dropdown {
  background: var(--color-bg-sidebar);
  border-color: rgba(255, 255, 255, 0.1);
  box-shadow:
    0 -4px 24px rgba(0, 0, 0, 0.4),
    0 2px 8px rgba(0, 0, 0, 0.3),
    inset 0 1px 0 rgba(255, 255, 255, 0.05);
}

html.dark .user-menu__item:hover {
  background: rgba(255, 255, 255, 0.08);
}

html.dark .user-menu__item--danger:hover {
  background: var(--color-danger-alpha-10);
}

/* ==================== 顶部导航 ==================== */

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: var(--header-height);
  padding: 0 var(--spacing-lg);
  background-color: var(--color-bg-header);
  border-bottom: 1px solid var(--color-border);
  z-index: var(--z-index-header);
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.header-right {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

/* 面包屑 */
.breadcrumb {
  display: flex;
  align-items: center;
}

.breadcrumb-home {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--color-text-secondary);
}

:deep(.el-breadcrumb__item) {
  font-size: var(--font-size-small);
}

:deep(.el-breadcrumb__inner) {
  color: var(--color-text-secondary);
  transition: color var(--transition-duration-fast) var(--transition-timing);
}

:deep(.el-breadcrumb__inner:hover) {
  color: var(--color-primary);
}

:deep(.el-breadcrumb__separator) {
  color: var(--color-text-muted);
}

/* 菜单按钮 */
.menu-btn {
  padding: var(--spacing-sm);
  border-radius: var(--radius-md);
  color: var(--color-text-secondary);
}

.menu-btn:hover {
  background-color: var(--color-bg-content);
  color: var(--color-primary);
}

/* 侧边栏展开/收起按钮 */
.sidebar-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  cursor: pointer;
  color: var(--color-text-secondary);
  transition: all var(--transition-duration-fast) var(--transition-timing);
}

.sidebar-toggle:hover {
  background-color: var(--color-bg-content);
  color: var(--color-primary);
}

/* 主题切换 - 顶部导航栏 */
.theme-toggle {
  cursor: pointer;
  padding: var(--spacing-xs);
}

.theme-toggle__track {
  width: 44px;
  height: 24px;
  border-radius: 12px;
  background: var(--color-bg-content);
  border: 1px solid var(--color-border);
  position: relative;
  transition: all var(--transition-duration-fast) var(--transition-timing);
}

.theme-toggle__track--dark {
  background: var(--color-primary);
  border-color: var(--color-primary);
}

.theme-toggle__thumb {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--color-bg-card);
  position: absolute;
  top: 1px;
  left: 1px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-secondary);
  transition: all var(--transition-duration-fast) var(--transition-timing);
  box-shadow: 0 2px 4px var(--color-black-alpha-10);
}

.theme-toggle__track--dark .theme-toggle__thumb {
  left: 21px;
  color: var(--color-primary);
}

/* 下拉菜单样式 */
:deep(.logout-item) {
  color: var(--color-danger);
}

/* 主题切换 - 已移除，移至侧边栏底部 */

/* 用户菜单 - 已移除，用户信息移至侧边栏底部 */

/* ==================== 移动端遮罩 ==================== */

.sidebar-overlay {
  position: fixed;
  left: 0;
  right: 0;
  top: 0;
  bottom: 0;
  background: var(--color-black-alpha-50);
  backdrop-filter: blur(4px);
  z-index: calc(var(--z-index-sidebar) - 1);
  transition: opacity var(--transition-duration-normal) var(--transition-timing);
}

/* 边缘滑动检测层 - 透明但可响应触摸 */
.edge-swipe-detector {
  position: fixed;
  left: 0;
  top: 0;
  width: 20%; /* 最大检测区域15-20% */
  height: 100vh;
  z-index: calc(var(--z-index-sidebar) - 2); /* 比遮罩层低，确保不阻挡其他交互 */
  /* 调试用 - 开发时可取消注释查看区域 */
  /* background: rgba(255, 0, 0, 0.1); */
}

/* ==================== 主内容区 ==================== */

.main-content {
  flex: 1;
  background-color: var(--color-bg-content);
  overflow-y: auto;
  height: calc(100vh - var(--header-height));
  padding: var(--spacing-lg);
}

/* ==================== 响应式 ==================== */

@media (max-width: 767px) {
  .main-content {
    padding: var(--spacing-md);
  }

  .header {
    padding: 0 var(--spacing-md);
  }
}

/* ==================== 过渡动画 ==================== */

.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--transition-duration-normal) var(--transition-timing);
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.fade-slide-enter-active,
.fade-slide-leave-active {
  transition:
    opacity var(--transition-duration-fast) var(--transition-timing),
    transform var(--transition-duration-fast) var(--transition-timing);
}

.fade-slide-enter-from,
.fade-slide-leave-to {
  opacity: 0;
  transform: translateX(-10px);
}

.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity var(--transition-duration-normal) var(--transition-timing);
}

.page-fade-enter-from,
.page-fade-leave-to {
  opacity: 0;
}

/* ==================== 响应式 ==================== */

@media (max-width: 767px) {
  .header {
    padding: 0 var(--spacing-md);
  }
}
</style>
