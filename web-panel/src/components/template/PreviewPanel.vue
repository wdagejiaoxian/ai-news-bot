<template>
  <div class="preview-panel">
    <div class="preview-header">
      <span class="preview-title">实时预览</span>
      <div class="preview-actions">
        <el-button
          size="small"
          :type="viewMode === 'rendered' ? 'primary' : 'default'"
          @click="viewMode = 'rendered'"
        >
          渲染视图
        </el-button>
        <el-button
          size="small"
          :type="viewMode === 'raw' ? 'primary' : 'default'"
          @click="viewMode = 'raw'"
        >
          原始视图
        </el-button>
        <el-button size="small" @click="refreshPreview" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <div class="preview-content" v-loading="loading">
      <!-- Empty state -->
      <div v-if="!templateContent" class="empty-preview">
        <div class="empty-icon">
          <el-icon :size="48"><Document /></el-icon>
        </div>
        <div class="empty-text">暂无模板内容</div>
        <div class="empty-hint">在左侧编辑器中输入模板内容，预览将实时显示</div>
      </div>

      <!-- Rendered view -->
      <div v-else-if="viewMode === 'rendered'" class="rendered-view">
        <div
          v-if="renderedContent"
          class="markdown-body"
          v-html="renderedContent"
        ></div>
        <div v-else-if="error" class="preview-error">
          <el-icon><Warning /></el-icon>
          <span>{{ error }}</span>
        </div>
      </div>

      <!-- Raw view -->
      <div v-else class="raw-view">
        <pre>{{ renderedContent || error || '无内容' }}</pre>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { request } from '@/api'

const props = defineProps<{
  templateContent: string
}>()

const loading = ref(false)
const renderedContent = ref('')
const error = ref('')
const viewMode = ref<'rendered' | 'raw'>('rendered')

// Debounce timer
let debounceTimer: ReturnType<typeof setTimeout> | null = null

// Watch for template changes with debounce
watch(
  () => props.templateContent,
  (newContent) => {
    if (debounceTimer) {
      clearTimeout(debounceTimer)
    }

    if (!newContent) {
      renderedContent.value = ''
      error.value = ''
      return
    }

    debounceTimer = setTimeout(() => {
      fetchPreview(newContent)
    }, 500)
  },
  { immediate: true }
)

async function fetchPreview(content: string) {
  loading.value = true
  error.value = ''

  try {
    const data = await request.post<{ rendered: string }>('/templates/preview', {
      template_content: content
    })

    renderedContent.value = data.rendered || ''
  } catch (e: any) {
    error.value = e.message || '预览生成失败'
    renderedContent.value = ''
  } finally {
    loading.value = false
  }
}

function refreshPreview() {
  if (props.templateContent) {
    fetchPreview(props.templateContent)
  }
}
</script>

<style scoped>
.preview-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  background: var(--el-bg-color);
  overflow: hidden;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--el-border-color);
  background: var(--el-fill-color-light);
}

.preview-title {
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.preview-actions {
  display: flex;
  gap: 8px;
}

.preview-content {
  flex: 1;
  overflow: auto;
  padding: 16px;
}

.empty-preview {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--el-text-color-secondary);
}

.empty-icon {
  margin-bottom: 16px;
  color: var(--el-text-color-placeholder);
}

.empty-text {
  font-size: 16px;
  font-weight: 500;
  margin-bottom: 8px;
}

.empty-hint {
  font-size: 13px;
  color: var(--el-text-color-placeholder);
}

.rendered-view {
  height: 100%;
  overflow: auto;
}

.markdown-body {
  font-size: 14px;
  line-height: 1.8;
  color: var(--el-text-color-primary);
  word-wrap: break-word;
  overflow-wrap: break-word;
}

/* 标题样式 */
.markdown-body :deep(h1) {
  font-size: 22px;
  font-weight: 700;
  margin: 0 0 16px;
  padding-bottom: 10px;
  border-bottom: 2px solid var(--el-border-color);
  color: var(--el-text-color-primary);
}

.markdown-body :deep(h2) {
  font-size: 18px;
  font-weight: 600;
  margin: 24px 0 12px;
  color: var(--el-text-color-primary);
}

.markdown-body :deep(h3) {
  font-size: 16px;
  font-weight: 600;
  margin: 18px 0 8px;
  color: var(--el-text-color-primary);
}

.markdown-body :deep(h4),
.markdown-body :deep(h5),
.markdown-body :deep(h6) {
  font-size: 14px;
  font-weight: 600;
  margin: 16px 0 8px;
  color: var(--el-text-color-primary);
}

/* 段落和列表 */
.markdown-body :deep(p) {
  margin: 12px 0;
  line-height: 1.7;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 12px 0;
  padding-left: 24px;
}

.markdown-body :deep(li) {
  margin: 6px 0;
  line-height: 1.6;
}

.markdown-body :deep(li > ul),
.markdown-body :deep(li > ol) {
  margin: 4px 0;
}

/* 代码样式 */
.markdown-body :deep(code) {
  background: var(--el-fill-color);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', monospace;
  font-size: 13px;
  color: var(--el-color-primary);
}

.markdown-body :deep(pre) {
  background: var(--el-fill-color-dark);
  padding: 16px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 12px 0;
  border: 1px solid var(--el-border-color);
}

.markdown-body :deep(pre code) {
  background: none;
  padding: 0;
  color: var(--el-text-color-primary);
  font-size: 13px;
  line-height: 1.5;
}

/* 引用块 */
.markdown-body :deep(blockquote) {
  margin: 16px 0;
  padding: 12px 16px;
  border-left: 4px solid var(--el-color-primary);
  background: var(--el-fill-color-light);
  color: var(--el-text-color-secondary);
  border-radius: 0 4px 4px 0;
}

.markdown-body :deep(blockquote p) {
  margin: 0;
}

/* 链接 */
.markdown-body :deep(a) {
  color: var(--el-color-primary);
  text-decoration: none;
  border-bottom: 1px dashed var(--el-color-primary-light-3);
  transition: all 0.2s;
}

.markdown-body :deep(a:hover) {
  text-decoration: none;
  border-bottom-color: var(--el-color-primary);
  color: var(--el-color-primary-light-3);
}

/* 强调 */
.markdown-body :deep(strong) {
  font-weight: 700;
  color: var(--el-text-color-primary);
}

.markdown-body :deep(em) {
  font-style: italic;
  color: var(--el-text-color-secondary);
}

/* 分隔线 */
.markdown-body :deep(hr) {
  margin: 24px 0;
  border: none;
  border-top: 1px solid var(--el-border-color);
}

/* 图片 */
.markdown-body :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 4px;
  margin: 8px 0;
}

/* 表格 */
.markdown-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 16px 0;
  font-size: 13px;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  padding: 10px 12px;
  border: 1px solid var(--el-border-color);
  text-align: left;
}

.markdown-body :deep(th) {
  background: var(--el-fill-color-light);
  font-weight: 600;
}

.markdown-body :deep(tr:nth-child(even)) {
  background: var(--el-fill-color-lighter);
}

.preview-error {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px;
  background: var(--el-color-danger-light-9);
  border-radius: 8px;
  color: var(--el-color-danger);
}

.raw-view {
  height: 100%;
}

.raw-view pre {
  margin: 0;
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', monospace;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-wrap: break-word;
  color: var(--el-text-color-primary);
}
</style>