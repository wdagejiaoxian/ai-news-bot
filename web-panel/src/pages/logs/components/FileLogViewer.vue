<template>
  <div class="file-log-viewer">
    <!-- 工具栏 -->
    <div class="toolbar">
      <el-select
        v-model="selectedFile"
        @change="handleFileChange"
        style="width: 190px"
        size="small"
      >
        <el-option
          v-for="f in fileList"
          :key="f.name"
          :label="f.name"
          :value="f.name"
        />
      </el-select>

      <el-select
        v-model="lineCount"
        @change="loadFile"
        style="width: 100px"
        size="small"
      >
        <el-option label="50 行" :value="50" />
        <el-option label="100 行" :value="100" />
        <el-option label="200 行" :value="200" />
        <el-option label="500 行" :value="500" />
      </el-select>

      <el-input
        v-model="keyword"
        placeholder="过滤日志..."
        clearable
        style="width: 200px"
        size="small"
      />

      <el-button size="small" @click="loadFile">
        <el-icon><Refresh /></el-icon>
        刷新
      </el-button>

      <span v-if="fileInfo" class="file-info">
        {{ filteredLines.length > 0 ? '显示 ' + displayLines.length + ' 行' : '' }}
        · 共 {{ fileInfo.total_lines }} 行 · {{ formatSize(fileInfo.file_size) }}
        <template v-if="fileInfo.truncated">
          <el-tag size="small" type="warning" style="margin-left: 4px">文件较大</el-tag>
        </template>
      </span>
    </div>

    <!-- 日志内容 -->
    <div
      ref="logContainer"
      class="log-content"
      v-loading="loading"
    >
      <div
        v-for="(line, i) in displayLines"
        :key="i"
        class="log-line"
        :class="getLineLevel(line.text)"
      >
        <span class="line-number">{{ line.index }}</span>
        <span class="line-text" v-html="highlightText(line.text, keyword)"></span>
      </div>

      <div v-if="!loading && filteredLines.length === 0" class="empty-state">
        <el-icon :size="32"><Document /></el-icon>
        <span>暂无日志内容</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Document, Refresh } from '@element-plus/icons-vue'
import {
  getLogFileList,
  readLogFile,
  type LogFileInfo,
  type LogLine,
} from '@/api/logs-file'

const loading = ref(false)
const fileList = ref<LogFileInfo[]>([])
const selectedFile = ref('app.log')
const lineCount = ref(100)
const keyword = ref('')

const rawLines = ref<LogLine[]>([])
const fileInfo = ref<{ total_lines: number; file_size: number; truncated: boolean } | null>(null)

/** 关键词过滤后的行 */
const filteredLines = computed(() => {
  if (!keyword.value) return rawLines.value
  const kw = keyword.value.toLowerCase()
  return rawLines.value.filter(l => l.text.toLowerCase().includes(kw))
})

/** 最多显示 500 行，避免 DOM 过多 */
const displayLines = computed(() => filteredLines.value.slice(0, 500))

/** 加载文件列表 */
async function loadFileList() {
  try {
    const data = await getLogFileList()
    fileList.value = data.files || []
    if (fileList.value.length > 0) {
      // 首页选中 app.log，如果不存在则选第一个
      const hasDefault = fileList.value.some(f => f.name === selectedFile.value)
      if (!hasDefault) {
        selectedFile.value = fileList.value[0].name
      }
    }
  } catch (e) {
    console.error('获取日志文件列表失败:', e)
  }
}

/** 读取文件内容 */
async function loadFile() {
  if (!selectedFile.value) return
  loading.value = true
  try {
    const data = await readLogFile({
      file: selectedFile.value,
      lines: lineCount.value,
    })
    rawLines.value = data.lines
    fileInfo.value = {
      total_lines: data.total_lines,
      file_size: data.file_size,
      truncated: data.truncated,
    }
  } catch (e) {
    console.error('读取日志文件失败:', e)
    rawLines.value = []
    fileInfo.value = null
  } finally {
    loading.value = false
  }
}

/** 切换文件 */
function handleFileChange() {
  loadFile()
}

/** 日志级别着色 */
function getLineLevel(text: string): string {
  if (text.includes(' - ERROR - ')) return 'log-error'
  if (text.includes(' - WARNING - ') || text.includes(' - WARN - ')) return 'log-warning'
  if (text.includes(' - DEBUG - ')) return 'log-debug'
  return 'log-info'
}

/** HTML 转义，防止 XSS */
function escapeHtml(text: string): string {
  const map: Record<string, string> = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;',
  }
  return text.replace(/[&<>"']/g, c => map[c] || c)
}

/** 关键词高亮：转义后包裹 <mark> 标签 */
function highlightText(text: string, kw: string): string {
  const escaped = escapeHtml(text)
  if (!kw) return escaped
  const regex = new RegExp(`(${escapeRegex(kw)})`, 'gi')
  return escaped.replace(regex, '<mark>$1</mark>')
}

/** 正则转义 */
function escapeRegex(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/** 文件大小格式化 */
function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

onMounted(async () => {
  await loadFileList()
  if (fileList.value.length > 0) {
    await loadFile()
  }
})
</script>

<style scoped>
.file-log-viewer {
  padding: 0;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.file-info {
  font-size: 12px;
  color: #909399;
  margin-left: auto;
  white-space: nowrap;
}

.log-content {
  background: #fafafa;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 0;
  max-height: 560px;
  overflow-y: auto;
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.7;
}

.log-line {
  display: flex;
  padding: 0 12px;
  line-height: 22px;
  border-bottom: 1px solid #f0f0f0;
}

.log-line:last-child {
  border-bottom: none;
}

.log-line:hover {
  background: #eef1f6;
}

.line-number {
  color: #c0c4cc;
  min-width: 48px;
  text-align: right;
  padding-right: 12px;
  user-select: none;
  flex-shrink: 0;
  font-size: 11px;
}

.line-text {
  white-space: pre-wrap;
  word-break: break-all;
  flex: 1;
}

/* ===== 级别着色 ===== */

/* ERROR：红底 + 左侧红色边框 */
.log-line.log-error {
  background: #fef0f0;
  color: #d0302f;
  border-left: 3px solid #f56c6c;
  padding-left: 9px;
}

.log-line.log-error:hover {
  background: #fde2e2;
}

.log-line.log-error .line-number {
  color: #f56c6c;
}

/* WARNING：橙底 + 左侧橙色边框 */
.log-line.log-warning {
  background: #fdf6ec;
  color: #b47c28;
  border-left: 3px solid #e6a23c;
  padding-left: 9px;
}

.log-line.log-warning:hover {
  background: #fce6c9;
}

.log-line.log-warning .line-number {
  color: #e6a23c;
}

/* DEBUG：灰色 */
.log-line.log-debug {
  color: #c0c4cc;
}

.log-line.log-debug .line-number {
  color: #dcdfe6;
}

/* INFO：默认 */
.log-line.log-info {
  color: #303133;
}

/* ===== 关键词高亮 ===== */
.log-line mark {
  background: #ffd54f;
  color: #333;
  padding: 0 2px;
  border-radius: 2px;
}

/* ===== 空状态 ===== */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 0;
  color: #c0c4cc;
  gap: 8px;
}

/* ===== 暗黑模式 ===== */
html.dark .log-content {
  background: #1d1e1f;
  border-color: #363637;
}

html.dark .log-line {
  border-bottom-color: #2a2a2b;
}

html.dark .log-line:hover {
  background: #2a2a2c;
}

html.dark .line-number {
  color: #5c5c5e;
}

html.dark .line-text {
  color: #cfd3dc;
}

html.dark .log-line.log-error {
  background: #2d1a1a;
  color: #e88080;
  border-left-color: #f56c6c;
}

html.dark .log-line.log-error:hover {
  background: #3a2020;
}

html.dark .log-line.log-error .line-number {
  color: #e88080;
}

html.dark .log-line.log-warning {
  background: #2d2515;
  color: #d9a84e;
  border-left-color: #e6a23c;
}

html.dark .log-line.log-warning:hover {
  background: #3a2f1a;
}

html.dark .log-line.log-warning .line-number {
  color: #d9a84e;
}

html.dark .log-line.log-debug {
  color: #5c5c5e;
}

html.dark .log-line.log-debug .line-number {
  color: #4a4a4b;
}

html.dark .log-line.log-info {
  color: #cfd3dc;
}

html.dark .log-line mark {
  background: #5c4400;
  color: #ffd54f;
}

html.dark .file-info {
  color: #5c5c5e;
}

html.dark .empty-state {
  color: #5c5c5e;
}
</style>
