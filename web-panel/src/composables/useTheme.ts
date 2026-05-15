/**
 * 主题管理 Composable
 *
 * 功能：
 * - 主题状态管理（亮色/暗色）
 * - localStorage 持久化
 * - 初始化时自动应用上次保存的主题
 *
 * @example
 * const { theme, isDark, toggleTheme } = useTheme()
 */
import { ref, watch, nextTick, onMounted, onUnmounted } from 'vue'

type Theme = 'light' | 'dark'
type Breakpoint = 'mobile' | 'tablet' | 'desktop'

const STORAGE_KEY = 'ai-news-bot-theme'

// 从 localStorage 读取主题
function getStoredTheme(): Theme {
  if (typeof window === 'undefined') return 'light'
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored === 'light' || stored === 'dark') return stored
  return 'light'
}

// 保存主题到 localStorage
function setStoredTheme(theme: Theme): void {
  if (typeof window === 'undefined') return
  localStorage.setItem(STORAGE_KEY, theme)
}

/**
 * 主题管理 hook
 */

// 模块级单例状态，确保所有调用者共享同一份响应式引用
const themeRef = ref<Theme>(getStoredTheme())
const isDarkRef = ref(themeRef.value === 'dark')

export function useTheme() {
  /**
   * 切换主题
   */
  function toggleTheme(): void {
    themeRef.value = themeRef.value === 'light' ? 'dark' : 'light'
  }

  /**
   * 设置指定主题
   */
  function setTheme(newTheme: Theme): void {
    themeRef.value = newTheme
  }

/**
  * 应用主题到 document
  */
  function applyTheme(newTheme: Theme): void {
    const root = document.documentElement
    if (newTheme === 'dark') {
      root.classList.add('dark')
    } else {
      root.classList.remove('dark')
    }

    // 强制重绘 - 解决 Element Plus 组件缓存样式不更新的问题
    // 方案：使用 display none -> offsetHeight -> display block 强制触发完整重排
    const body = document.body
    const originalDisplay = body.style.display
    body.style.display = 'none'
    // eslint-disable-next-line no-unused-expressions
    body.offsetHeight // 触发一次 reflow
    body.style.display = originalDisplay
  }

  // 监听主题变化
  watch(themeRef, async (newTheme) => {
    // 1. 先更新响应式状态 → Vue 处理 computed 重求值 → VChart 收到新 option 并渲染
    isDarkRef.value = newTheme === 'dark'
    setStoredTheme(newTheme)
    // 2. 等 Vue 完成本轮响应式更新（图表颜色已切换完毕）
    await nextTick()
    // 3. 再强制重绘（修复 Element Plus 组件缓存样式）
    applyTheme(newTheme)
  }, { immediate: false })

  // 初始化
  onMounted(() => {
    applyTheme(themeRef.value)
  })

  return {
    theme: themeRef,
    isDark: isDarkRef,
    toggleTheme,
    setTheme,
  }
}

/**
 * 响应式断点 hook
 * 使用 CSS 变量定义的断点值
 */
export function useResponsive() {
  // 从 CSS 变量读取断点值
  const getBreakpoints = () => ({
    mobile: parseInt(getComputedStyle(document.documentElement).getPropertyValue('--breakpoint-sm')) || 767,
    tablet: parseInt(getComputedStyle(document.documentElement).getPropertyValue('--breakpoint-lg')) || 1024,
  })

  const width = ref(typeof window !== 'undefined' ? window.innerWidth : 1200)

  const breakpoint = ref<Breakpoint>('desktop')
  const isMobile = ref(false)
  const isTablet = ref(false)
  const isDesktop = ref(true)

  // 防抖处理 resize 事件
  let resizeTimer: ReturnType<typeof setTimeout> | null = null

  function updateBreakpoint(): void {
    const BREAKPOINTS = getBreakpoints()
    if (width.value < BREAKPOINTS.mobile) {
      breakpoint.value = 'mobile'
    } else if (width.value < BREAKPOINTS.tablet) {
      breakpoint.value = 'tablet'
    } else {
      breakpoint.value = 'desktop'
    }
    isMobile.value = breakpoint.value === 'mobile'
    isTablet.value = breakpoint.value === 'tablet'
    isDesktop.value = breakpoint.value === 'desktop'
  }

  function handleResize(): void {
    if (resizeTimer) clearTimeout(resizeTimer)
    resizeTimer = setTimeout(() => {
      width.value = window.innerWidth
      updateBreakpoint()
    }, 100) // 100ms 防抖
  }

  function cleanup(): void {
    if (resizeTimer) clearTimeout(resizeTimer)
    window.removeEventListener('resize', handleResize)
  }

  onMounted(() => {
    updateBreakpoint()
    window.addEventListener('resize', handleResize)
  })

  onUnmounted(() => {
    cleanup()
  })

  return {
    width,
    breakpoint,
    isMobile,
    isTablet,
    isDesktop,
    cleanup,
  }
}
