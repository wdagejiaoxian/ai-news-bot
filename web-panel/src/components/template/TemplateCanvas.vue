<template>
  <div class="template-canvas" :class="{ 'has-error': (errors?.length ?? 0) > 0 }">
    <div class="canvas-header">
      <span class="canvas-title">模板内容</span>
      <span v-if="(errors?.length ?? 0) > 0" class="error-badge">
        <el-icon><Warning /></el-icon>
        {{ errors?.length ?? 0 }} 个错误
      </span>
    </div>

    <div class="editor-wrapper">
      <div class="line-numbers" ref="lineNumbersRef">
        <div
          v-for="n in lineCount"
          :key="n"
          class="line-number"
        >
          {{ n }}
        </div>
      </div>

      <div class="textarea-container" ref="textareaContainerRef">
        <textarea
          ref="textareaRef"
          v-model="content"
          class="template-textarea"
          :class="{ 'has-errors': (errors?.length ?? 0) > 0 }"
          placeholder="输入 Markdown 模板内容...

使用 {&#123;variable&#125;} 插入变量
使用 {&#123;#github_loop&#125;}...{&#123;/github_loop&#125;} 插入 GitHub 循环
使用 {&#123;#article_loop&#125;}...{&#123;/article_loop&#125;} 插入文章循环"
          @input="handleInput"
          @scroll="syncScroll"
          @click="updateCursorPosition"
          @keyup="updateCursorPosition"
          @mousemove="handleMouseMove"
        ></textarea>

        <!-- 变量悬浮提示层 -->
        <div
          v-if="hoveredVariable"
          class="variable-tooltip"
          :style="tooltipStyle"
        >
          <div class="tooltip-header">{{ hoveredVariable.key }}</div>
          <div class="tooltip-desc">{{ hoveredVariable.description }}</div>
          <div v-if="hoveredVariable.loopHint" class="tooltip-hint">
            <el-icon><InfoFilled /></el-icon>
            {{ hoveredVariable.loopHint }}
          </div>
        </div>
      </div>
    </div>

    <!-- Error details -->
    <div v-if="(errors?.length ?? 0) > 0" class="error-details">
      <div v-for="(error, index) in (errors ?? [])" :key="index" class="error-item">
        <el-icon><Warning /></el-icon>
        <span>{{ error }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive } from 'vue'

interface VariableInfo {
  key: string
  description: string
  loopHint?: string
}

// 上下文变量
const contextVariables: VariableInfo[] = [
  { key: '{{date}}', description: '当前日期，格式：YYYY-MM-DD' },
  { key: '{{week_start}}', description: '本周开始日期' },
  { key: '{{week_end}}', description: '本周结束日期' },
  { key: '{{generated_at}}', description: '报告生成时间' },
  { key: '{{week_number}}', description: '年内周序号' },
  { key: '{{github_count}}', description: 'GitHub 项目总数' },
  { key: '{{app_name}}', description: '应用名称：AI News Bot' },
]

// GitHub 循环变量
const githubVariables: VariableInfo[] = [
  { key: '{{github.full_name}}', description: '项目全名 (owner/repo)' },
  { key: '{{github.url}}', description: '项目 URL 地址' },
  { key: '{{github.stars}}', description: '星标数量' },
  { key: '{{github.stars_today}}', description: '今日新增星标' },
  { key: '{{github.language}}', description: '主要编程语言' },
  { key: '{{github.description}}', description: '项目描述' },
  { key: '{{github.index}}', description: '序号 (从 1 开始)' },
]

// 文章循环变量
const articleVariables: VariableInfo[] = [
  { key: '{{article.title}}', description: '文章标题' },
  { key: '{{article.url}}', description: '文章 URL 地址' },
  { key: '{{article.score}}', description: 'AI 评分 (0-100)' },
  { key: '{{article.summary}}', description: 'AI 生成的摘要' },
  { key: '{{article.tags}}', description: '文章标签 (逗号分隔)' },
  { key: '{{article.source_name}}', description: '文章来源名称' },
  { key: '{{article.index}}', description: '序号 (从 1 开始)' },
]

// 循环块
const loopBlocks = [
  { key: '{{#github_loop}}', description: 'GitHub 项目循环开始', loopHint: '在此块内使用 GitHub 变量' },
  { key: '{{/github_loop}}', description: 'GitHub 项目循环结束' },
  { key: '{{#article_loop}}', description: '文章循环开始', loopHint: '在此块内使用文章变量' },
  { key: '{{/article_loop}}', description: '文章循环结束' },
]

// 所有变量（用于快速查找）
const allVariables = [...contextVariables, ...githubVariables, ...articleVariables, ...loopBlocks]

const props = defineProps<{
  modelValue: string
  errors?: string[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  'change': [value: string]
  'cursor-change': [position: number]
}>()

const textareaRef = ref<HTMLTextAreaElement | null>(null)
const lineNumbersRef = ref<HTMLDivElement | null>(null)
const textareaContainerRef = ref<HTMLDivElement | null>(null)
const cursorPosition = ref(0)

// 悬浮变量状态
const hoveredVariable = ref<VariableInfo | null>(null)
const tooltipStyle = reactive({
  top: '0px',
  left: '0px',
})

const content = computed({
  get: () => props.modelValue,
  set: (value: string) => emit('update:modelValue', value)
})

const lineCount = computed(() => {
  const lines = content.value.split('\n').length
  return Math.max(lines, 20)
})

function handleInput(e: Event) {
  const target = e.target as HTMLTextAreaElement
  emit('change', target.value)
}

function updateCursorPosition() {
  if (textareaRef.value) {
    cursorPosition.value = textareaRef.value.selectionStart
    emit('cursor-change', cursorPosition.value)
  }
}

function syncScroll() {
  if (textareaRef.value && lineNumbersRef.value) {
    lineNumbersRef.value.scrollTop = textareaRef.value.scrollTop
  }
}

// 查找光标位置处的变量
function findVariableAtPosition(text: string, position: number): VariableInfo | null {
  // 向前查找最近的 {{ 或 }}
  const beforeCursor = text.substring(0, position)
  const afterCursor = text.substring(position)

  // 匹配 {{...}} 模式
  const varPattern = /\{\{[^}]+\}\}/g

  // 在光标前后的文本中查找变量
  let match
  const allMatches: { match: RegExpExecArray; start: number; end: number }[] = []

  // 重置正则状态
  varPattern.lastIndex = 0
  while ((match = varPattern.exec(text)) !== null) {
    allMatches.push({
      match,
      start: match.index,
      end: match.index + match[0].length,
    })
  }

  // 找到包含光标位置的变量
  for (const m of allMatches) {
    if (position >= m.start && position <= m.end) {
      // 找到了，查找详细信息
      return findVariableInfo(m.match[0])
    }
  }

  // 如果光标不在变量内，查找光标前的最后一个变量
  const lastMatchBefore = allMatches
    .filter(m => m.end <= position)
    .pop()

  if (lastMatchBefore) {
    return findVariableInfo(lastMatchBefore.match[0])
  }

  return null
}

function findVariableInfo(varKey: string): VariableInfo | null {
  return allVariables.find(v => v.key === varKey) || null
}

// 处理鼠标移动
function handleMouseMove(e: MouseEvent) {
  if (!textareaRef.value) return

  const textarea = textareaRef.value
  const text = textarea.value
  const cursorPos = textarea.selectionStart

  // 获取光标位置文本
  const variable = findVariableAtPosition(text, cursorPos)

  if (variable) {
    hoveredVariable.value = variable

    // 计算 tooltip 位置
    const rect = textarea.getBoundingClientRect()
    const containerRect = textareaContainerRef.value?.getBoundingClientRect()

    if (containerRect) {
      tooltipStyle.top = `${e.clientY - containerRect.top + 10}px`
      tooltipStyle.left = `${e.clientX - containerRect.left + 10}px`
    }
  } else {
    hoveredVariable.value = null
  }
}

// Insert text at cursor position
function insertAtCursor(text: string) {
  if (!textareaRef.value) return

  const textarea = textareaRef.value
  const start = textarea.selectionStart
  const end = textarea.selectionEnd
  const before = content.value.substring(0, start)
  const after = content.value.substring(end)

  content.value = before + text + after

  // Set cursor position after inserted text
  setTimeout(() => {
    if (textareaRef.value) {
      textareaRef.value.selectionStart = textareaRef.value.selectionEnd = start + text.length
      textareaRef.value.focus()
    }
  }, 0)
}

// Expose insert method
defineExpose({
  insertAtCursor
})
</script>

<style scoped>
.template-canvas {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--el-bg-color);
}

.template-canvas.has-error {
  border-color: var(--el-color-danger);
}

.canvas-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--el-border-color);
  background: var(--el-fill-color-light);
}

.canvas-title {
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.error-badge {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  background: var(--el-color-danger-light-9);
  color: var(--el-color-danger);
  border-radius: 4px;
  font-size: 12px;
}

.editor-wrapper {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.line-numbers {
  flex-shrink: 0;
  width: 40px;
  padding: 12px 0;
  background: var(--el-fill-color);
  border-right: 1px solid var(--el-border-color);
  overflow: hidden;
  text-align: right;
  user-select: none;
}

.line-number {
  padding: 0 8px;
  line-height: 1.6;
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', monospace;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.textarea-container {
  position: relative;
  flex: 1;
  overflow: hidden;
}

.template-textarea {
  width: 100%;
  height: 100%;
  padding: 12px 16px;
  border: none;
  outline: none;
  resize: none;
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', monospace;
  font-size: 13px;
  line-height: 1.6;
  color: var(--el-text-color-primary);
  background: var(--el-bg-color);
  caret-color: var(--el-color-primary);
}

.template-textarea.has-errors {
  color: var(--el-color-danger);
}

.template-textarea::placeholder {
  color: var(--el-text-color-placeholder);
}

/* 变量悬浮提示 */
.variable-tooltip {
  position: absolute;
  z-index: 100;
  padding: 10px 14px;
  background: var(--el-bg-color-overlay);
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
  pointer-events: none;
  max-width: 280px;
  animation: tooltipFadeIn 0.15s ease;
}

@keyframes tooltipFadeIn {
  from {
    opacity: 0;
    transform: translateY(-4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.tooltip-header {
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', monospace;
  font-size: 13px;
  font-weight: 600;
  color: var(--el-color-primary);
  margin-bottom: 6px;
  padding-bottom: 6px;
  border-bottom: 1px dashed var(--el-border-color);
}

.tooltip-desc {
  font-size: 13px;
  color: var(--el-text-color-primary);
  line-height: 1.5;
}

.tooltip-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--el-border-color);
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.error-details {
  padding: 12px 16px;
  background: var(--el-color-danger-light-9);
  border-top: 1px solid var(--el-color-danger-light-7);
}

.error-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  font-size: 12px;
  color: var(--el-color-danger);
}
</style>