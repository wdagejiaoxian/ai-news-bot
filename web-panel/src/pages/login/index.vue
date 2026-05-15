<template>
  <div class="login-container">
    <!-- 左侧插画区域 -->
    <div class="login-illustration">
      <div class="illustration-content">
        <svg
          class="illustration-svg"
          viewBox="0 0 400 400"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <!-- 外圈 -->
          <circle cx="200" cy="200" r="150" :stroke="svgColors.circle" stroke-width="2" stroke-dasharray="8 8" opacity="0.8" />
          <!-- 中圈 -->
          <circle cx="200" cy="200" r="120" :stroke="svgColors.circle" stroke-width="2" stroke-dasharray="4 4" opacity="0.6" />
          <!-- 中心填充圆 -->
          <circle cx="200" cy="200" r="60" :fill="svgColors.circle" opacity="0.15" />
          <circle cx="200" cy="200" r="45" :fill="svgColors.circle" opacity="0.2" />
          <circle cx="200" cy="200" r="30" :fill="svgColors.fill" />
          <!-- 节点 -->
          <g class="nodes">
            <circle cx="200" cy="100" r="8" :fill="svgColors.fill" />
            <circle cx="120" cy="160" r="6" :fill="svgColors.node" />
            <circle cx="280" cy="160" r="6" :fill="svgColors.node" />
            <circle cx="140" cy="280" r="6" :fill="svgColors.node" />
            <circle cx="260" cy="280" r="6" :fill="svgColors.node" />
            <circle cx="200" cy="320" r="8" :fill="svgColors.fill" />
          </g>
          <!-- 连接线 -->
          <g class="connections" :stroke="svgColors.line" stroke-width="1.5">
            <line x1="200" y1="100" x2="200" y2="155" />
            <line x1="120" y1="160" x2="160" y2="180" />
            <line x1="280" y1="160" x2="240" y2="180" />
            <line x1="200" y1="245" x2="140" y2="274" />
            <line x1="200" y1="245" x2="260" y2="274" />
            <line x1="200" y1="320" x2="200" y2="245" />
          </g>
          <!-- 装饰点 -->
          <g class="dots" :fill="svgColors.dot">
            <circle cx="80" cy="120" r="3" opacity="0.6" />
            <circle cx="320" cy="100" r="4" opacity="0.4" />
            <circle cx="60" cy="260" r="4" opacity="0.5" />
            <circle cx="340" cy="280" r="3" opacity="0.6" />
            <circle cx="160" cy="60" r="3" opacity="0.4" />
            <circle cx="280" cy="340" r="4" opacity="0.5" />
          </g>
        </svg>
      </div>

      <div class="illustration-tagline">
        <h2 class="tagline-title">AI News Bot</h2>
        <p class="tagline-desc">智能资讯采集 · 自动摘要 · 精准推送</p>
      </div>
    </div>

    <!-- 右侧登录表单 -->
    <div class="login-form-wrapper">
      <div class="login-form-container">
        <div class="form-header">
          <h1 class="form-title">欢迎回来</h1>
          <p class="form-subtitle">登录到 AI News Bot 管理面板</p>
        </div>

        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          label-width="0"
          class="login-form"
          @submit.prevent="handleLogin"
        >
          <el-form-item prop="username" class="form-item">
            <el-input
              v-model="form.username"
              placeholder="请输入用户名"
              size="large"
              clearable
              class="custom-input"
              @keyup.enter="handleKeyup"
            >
              <template #prefix>
                <el-icon class="input-icon"><User /></el-icon>
              </template>
            </el-input>
          </el-form-item>

          <el-form-item prop="password" class="form-item">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="请输入密码"
              size="large"
              show-password
              class="custom-input"
              @keyup.enter="handleKeyup"
            >
              <template #prefix>
                <el-icon class="input-icon"><Lock /></el-icon>
              </template>
            </el-input>
          </el-form-item>

          <el-form-item class="form-item form-item--btn">
            <el-button
              type="primary"
              :loading="loading"
              size="large"
              class="login-btn"
              @click="handleLogin"
            >
              {{ loading ? '登录中...' : '登录' }}
            </el-button>
          </el-form-item>
        </el-form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { useUserStore } from '@/store'

const router = useRouter()
const userStore = useUserStore()

const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({
  username: '',
  password: '',
})

// 检测是否启用减少动画
const prefersReducedMotion = ref(
  window.matchMedia('(prefers-reduced-motion: reduce)').matches
)

// SVG 颜色（适配暗黑模式）
const svgColors = computed(() => {
  const isDark = document.documentElement.classList.contains('dark')
  return {
    circle: isDark ? 'rgba(96, 165, 250, 0.4)' : 'rgba(255, 255, 255, 0.3)',
    line: isDark ? 'rgba(96, 165, 250, 0.5)' : 'rgba(255, 255, 255, 0.5)',
    node: isDark ? 'rgba(96, 165, 250, 0.9)' : 'rgba(255, 255, 255, 0.9)',
    dot: isDark ? 'rgba(96, 165, 250, 0.7)' : 'rgba(255, 255, 255, 0.8)',
    fill: isDark ? 'rgba(96, 165, 250, 0.9)' : 'rgba(255, 255, 255, 0.9)',
  }
})

const rules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度至少6位', trigger: 'blur' },
  ],
}

// 监听主题变化，更新 SVG 颜色
function updateSvgColors() {
  // 强制触发响应式更新
  svgColors.value // 引用以触发更新
}

// 回车键提交
function handleKeyup(event: KeyboardEvent): void {
  if (event.key === 'Enter' && !loading.value) {
    handleLogin()
  }
}

async function handleLogin(): Promise<void> {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    loading.value = true
    try {
      await userStore.login(form.username, form.password)
      ElMessage.success('登录成功')
      router.push('/dashboard')
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } }
      ElMessage.error(err.response?.data?.detail || '登录失败')
    } finally {
      loading.value = false
    }
  })
}
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  background-color: var(--color-bg-page);
}

/* 左侧插画 */
.login-illustration {
  flex: 0 0 45%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-hover) 50%, var(--color-primary-darker) 100%);
  padding: var(--spacing-3xl);
  position: relative;
  overflow: hidden;
}

/* 背景装饰圆形 */
.login-illustration::before {
  content: '';
  position: absolute;
  width: 500px;
  height: 500px;
  border-radius: 50%;
  background: radial-gradient(circle, var(--color-white-alpha-10) 0%, transparent 70%);
  top: -150px;
  right: -150px;
  animation: pulse 8s ease-in-out infinite;
}

.login-illustration::after {
  content: '';
  position: absolute;
  width: 300px;
  height: 300px;
  border-radius: 50%;
  background: radial-gradient(circle, var(--color-white-alpha-08) 0%, transparent 70%);
  bottom: -80px;
  left: -80px;
  animation: pulse 6s ease-in-out infinite reverse;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 0.6; }
  50% { transform: scale(1.05); opacity: 0.8; }
}

.illustration-content {
  width: 100%;
  max-width: 320px;
  aspect-ratio: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  z-index: 1;
}

.illustration-svg {
  width: 100%;
  height: 100%;
  animation: float 8s ease-in-out infinite;
  filter: drop-shadow(0 10px 30px rgba(0, 0, 0, 0.2));
}

@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-8px); }
}

/* 节点呼吸动画 - 简化 */
.nodes circle {
  animation: breathe 4s ease-in-out infinite;
}

.nodes circle:nth-child(1) { animation-delay: 0s; }
.nodes circle:nth-child(2) { animation-delay: 0.4s; }
.nodes circle:nth-child(3) { animation-delay: 0.8s; }
.nodes circle:nth-child(4) { animation-delay: 1.2s; }
.nodes circle:nth-child(5) { animation-delay: 1.6s; }
.nodes circle:nth-child(6) { animation-delay: 2s; }

@keyframes breathe {
  0%, 100% { opacity: 0.7; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.08); }
}

/* 连接线流动动画 - 简化 */
.connections line {
  stroke-dasharray: 100;
  stroke-dashoffset: 100;
  animation: flow 4s ease-in-out infinite;
}

.connections line:nth-child(1) { animation-delay: 0s; }
.connections line:nth-child(2) { animation-delay: 0.3s; }
.connections line:nth-child(3) { animation-delay: 0.6s; }
.connections line:nth-child(4) { animation-delay: 0.9s; }
.connections line:nth-child(5) { animation-delay: 1.2s; }
.connections line:nth-child(6) { animation-delay: 1.5s; }

@keyframes flow {
  0% { stroke-dashoffset: 100; opacity: 0.5; }
  50% { stroke-dashoffset: 0; opacity: 1; }
  100% { stroke-dashoffset: -100; opacity: 0.5; }
}

/* 装饰点漂浮动画 - 简化 */
.dots circle {
  animation: drift 5s ease-in-out infinite;
}

.dots circle:nth-child(1) { animation-delay: 0s; animation-duration: 4s; }
.dots circle:nth-child(2) { animation-delay: 0.5s; animation-duration: 5s; }
.dots circle:nth-child(3) { animation-delay: 1s; animation-duration: 4.5s; }
.dots circle:nth-child(4) { animation-delay: 1.5s; animation-duration: 5.5s; }
.dots circle:nth-child(5) { animation-delay: 2s; animation-duration: 4s; }
.dots circle:nth-child(6) { animation-delay: 2.5s; animation-duration: 5s; }

@keyframes drift {
  0%, 100% { transform: translateY(0) translateX(0); opacity: 0.4; }
  25% { transform: translateY(-8px) translateX(4px); opacity: 0.7; }
  50% { transform: translateY(-4px) translateX(-4px); opacity: 0.5; }
  75% { transform: translateY(-12px) translateX(2px); opacity: 0.6; }
}

.illustration-tagline {
  text-align: center;
  margin-top: var(--spacing-xl);
  position: relative;
  z-index: 1;
}

.tagline-title {
  font-family: var(--font-family-display);
  font-size: var(--font-size-h2);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-inverse);
  margin: 0 0 var(--spacing-sm) 0;
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.tagline-desc {
  font-size: var(--font-size-body);
  color: var(--color-text-inverse-alpha-85);
  margin: 0;
}

/* 右侧表单 */
.login-form-wrapper {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-3xl);
  background-color: var(--color-bg-page);
}

.login-form-container {
  width: 100%;
  max-width: 400px;
  padding: var(--spacing-2xl);
  border-radius: var(--radius-2xl);
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  box-shadow: var(--shadow-brand);
}

.form-header {
  margin-bottom: var(--spacing-xl);
  text-align: center;
}

.form-title {
  font-family: var(--font-family-display);
  font-size: var(--font-size-h1);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  margin: 0 0 var(--spacing-sm) 0;
}

.form-subtitle {
  font-size: var(--font-size-body);
  color: var(--color-text-secondary);
  margin: 0;
}

.login-form {
  margin-top: var(--spacing-lg);
}

.form-item {
  margin-bottom: var(--spacing-md);
}

.form-item--btn {
  margin-top: var(--spacing-lg);
  margin-bottom: 0;
}

/* 输入框样式 */
.custom-input {
  height: 48px;
}

.custom-input :deep(.el-input__wrapper) {
  padding: 0 var(--spacing-md);
  height: 100%;
  border-radius: var(--radius-md);
  background-color: var(--color-bg-card);
  border: 1px solid var(--color-border);
  box-shadow: none;
  transition: all var(--transition-duration-fast) var(--transition-timing);
}

.custom-input :deep(.el-input__wrapper:hover) {
  border-color: var(--color-primary);
}

.custom-input :deep(.el-input__wrapper.is-focus) {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px var(--color-primary-alpha-10);
}

.custom-input :deep(.el-input__inner) {
  height: 100%;
  font-size: var(--font-size-body);
  color: var(--color-text-primary);
}

.custom-input :deep(.el-input__inner::placeholder) {
  color: var(--color-text-muted);
}

.input-icon {
  color: var(--color-text-muted);
  font-size: 16px;
}

/* 登录按钮 */
.login-btn {
  width: 100%;
  height: 48px;
  font-size: var(--font-size-body);
  font-weight: var(--font-weight-semibold);
  border-radius: var(--radius-md);
  background-color: var(--color-primary);
  border-color: var(--color-primary);
  transition: all var(--transition-duration-fast) var(--transition-timing);
}

.login-btn:hover {
  background-color: var(--color-primary-hover);
  border-color: var(--color-primary-hover);
  transform: translateY(-2px);
  box-shadow: 0 8px 20px var(--color-primary-alpha-30);
}

.login-btn:active {
  transform: translateY(0) scale(0.98);
  box-shadow: none;
}

/* 键盘焦点样式 */
.login-btn:focus-visible,
.custom-input:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

/* 减少动画 - 适配 prefers-reduced-motion */
@media (prefers-reduced-motion: reduce) {
  .login-illustration::before,
  .login-illustration::after,
  .illustration-svg,
  .nodes circle,
  .connections line,
  .dots circle {
    animation: none !important;
  }

  .login-btn:hover {
    transform: none;
  }
}

/* 表单底部 */
/* 响应式 */
@media (max-width: 767px) {
  .login-container {
    flex-direction: column;
  }

  .login-illustration {
    display: flex;
    flex: 0 0 auto;
    flex-direction: row;
    justify-content: center;
    padding: var(--spacing-lg);
    min-height: auto;
  }

  .login-illustration::before,
  .login-illustration::after {
    display: none;
  }

  .illustration-content {
    display: none;
  }

  .illustration-tagline {
    display: flex;
    flex-direction: row;
    align-items: center;
    gap: var(--spacing-md);
    margin: 0;
  }

  .tagline-title {
    font-size: var(--font-size-h4);
  }

  .tagline-desc {
    display: none;
  }

  .login-form-wrapper {
    max-width: 100%;
    padding: var(--spacing-md) var(--spacing-lg) var(--spacing-2xl);
    flex: 1;
  }

  .login-form-container {
    max-width: 100%;
    padding: var(--spacing-lg);
    border-radius: var(--radius-lg);
  }
}

@media (min-width: 768px) and (max-width: 1023px) {
  .illustration-content {
    max-width: 300px;
  }

  .tagline-title {
    font-size: var(--font-size-h3);
  }
}
</style>
