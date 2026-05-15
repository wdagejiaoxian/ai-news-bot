<template>
  <CustomDialog
    v-model="dialogVisible"
    title="编辑模板"
    size="xlarge"
    :close-on-click-overlay="false"
    @close="handleDialogClose"
  >
    <div class="editor-layout">
      <!-- 顶部工具栏 -->
      <div class="toolbar">
        <div class="toolbar-left">
          <span class="toolbar-label">模板类型：</span>
          <el-radio-group v-model="currentType" @change="handleTypeChange" size="small">
            <el-radio-button value="daily">日报</el-radio-button>
            <el-radio-button value="weekly">周报</el-radio-button>
            <el-radio-button value="immediate">即时推送</el-radio-button>
          </el-radio-group>
        </div>
        <div class="toolbar-right">
          <el-dropdown @command="handleLoadPreset" trigger="click" size="small">
            <el-button size="small">
              加载预设
              <el-icon class="el-icon--right"><ArrowDown /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item
                  v-for="preset in presetTemplates"
                  :key="preset.key"
                  :command="preset.key"
                >
                  <div class="preset-option">
                    <span class="preset-name">{{ preset.name }}</span>
                    <span class="preset-desc">{{ preset.description }}</span>
                  </div>
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-button size="small" @click="handleImport">
            <el-icon><Upload /></el-icon>
            导入
          </el-button>
          <el-button size="small" @click="handleExport" :disabled="!currentTemplate">
            <el-icon><Download /></el-icon>
            导出
          </el-button>
        </div>
      </div>

      <!-- 循环块工具 -->
      <div class="loop-tools">
        <span class="tools-label">插入循环块：</span>
        <el-button size="small" type="primary" plain @click="handleInsertLoop('github_loop')">
          <el-icon><Connection /></el-icon>
          GitHub 循环
        </el-button>
        <el-button size="small" type="primary" plain @click="handleInsertLoop('article_loop')">
          <el-icon><Document /></el-icon>
          文章循环
        </el-button>
      </div>

      <!-- 变量选择面板 -->
      <div class="variable-panel">
        <div class="panel-section">
          <span class="section-label">上下文变量：</span>
          <div class="var-list">
            <el-tooltip
              v-for="v in contextVariables"
              :key="v.key"
              :content="v.description"
              placement="top"
            >
              <el-tag
                class="var-tag"
                @click="handleInsertVariable(v.key)"
              >
                {{ v.key }}
              </el-tag>
            </el-tooltip>
          </div>
        </div>
        <el-divider direction="vertical" />
        <div class="panel-section">
          <span class="section-label">GitHub 变量：</span>
          <div class="var-list">
            <el-tooltip
              v-for="v in githubVariables"
              :key="v.key"
              :content="v.description"
              placement="top"
            >
              <el-tag
                class="var-tag github"
                @click="handleInsertVariable(v.key)"
              >
                {{ v.key }}
              </el-tag>
            </el-tooltip>
          </div>
        </div>
        <el-divider direction="vertical" />
        <div class="panel-section">
          <span class="section-label">文章变量：</span>
          <div class="var-list">
            <el-tooltip
              v-for="v in articleVariables"
              :key="v.key"
              :content="v.description"
              placement="top"
            >
              <el-tag
                class="var-tag article"
                @click="handleInsertVariable(v.key)"
              >
                {{ v.key }}
              </el-tag>
            </el-tooltip>
          </div>
        </div>
      </div>

      <!-- 模板编辑器 -->
      <div class="template-editor-wrapper">
        <TemplateCanvas
          ref="canvasRef"
          v-model="currentTemplate"
          :errors="validationErrors"
          @change="handleTemplateChange"
        />
      </div>
    </div>

    <template #footer-left>
      <el-button v-if="currentTemplateId" type="danger" plain @click="handleDelete">
        <el-icon><Delete /></el-icon>
        删除模板
      </el-button>
      <el-button v-if="currentTemplateId" type="info" plain @click="handleCopyToOther">
        <el-icon><CopyDocument /></el-icon>
        复制到其他 Webhook
      </el-button>
    </template>

    <template #footer-right>
      <el-button type="primary" @click="handleSave" :loading="saving">
        <el-icon><Check /></el-icon>
        保存模板
      </el-button>
    </template>

    <!-- 复制到其他 Webhook 弹窗 -->
    <el-dialog
      v-model="copyDialogVisible"
      title="复制模板到其他 Webhook"
      width="400px"
      append-to-body
    >
      <el-form-item label="选择 Webhook">
        <el-select v-model="targetWebhookId" placeholder="请选择目标 Webhook" filterable>
          <el-option
            v-for="wh in webhookList"
            :key="wh.id"
            :label="wh.name"
            :value="wh.id"
          />
        </el-select>
      </el-form-item>
      <template #footer>
        <el-button @click="copyDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmCopy" :loading="copying">确认复制</el-button>
      </template>
    </el-dialog>

    <!-- 导入弹窗 -->
    <el-dialog
      v-model="importDialogVisible"
      title="导入模板"
      width="500px"
      append-to-body
    >
      <el-input
        v-model="importContent"
        type="textarea"
        :rows="10"
        placeholder="粘贴模板 JSON 内容..."
      />
      <template #footer>
        <el-button @click="importDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmImport">确认导入</el-button>
      </template>
    </el-dialog>
  </CustomDialog>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { request } from '@/api'
import type { Webhook } from '@/types/api'
import TemplateCanvas from './TemplateCanvas.vue'
import CustomDialog from '@/components/ui/CustomDialog.vue'

interface Template {
  id?: number
  webhook_config_id: number
  template_type: string
  template_name: string
  template_content: string
  is_active: boolean
  created_at?: string
  updated_at?: string
}

interface PresetTemplate {
  key: string
  name: string
  type: string
  description: string
  content: string
}

interface ValidationResult {
  valid: boolean
  errors: string[]
  warnings: string[]
}

const props = defineProps<{
  visible: boolean
  webhookId: number
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  'saved': []
}>()

// Refs
const canvasRef = ref<InstanceType<typeof TemplateCanvas> | null>(null)

// State
const currentType = ref<'daily' | 'weekly' | 'immediate'>('daily')
const currentTemplate = ref('')
const currentTemplateId = ref<number | null>(null)
const templateName = ref('')
const saving = ref(false)
const validationErrors = ref<string[]>([])
const hasUnsavedChanges = ref(false)

// Preset templates
const presetTemplates = ref<PresetTemplate[]>([])
const webhookList = ref<Webhook[]>([])

// Dialogs
const copyDialogVisible = ref(false)
const targetWebhookId = ref<number | null>(null)
const copying = ref(false)
const importDialogVisible = ref(false)
const importContent = ref('')

// Computed for CustomDialog v-model
const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val)
})

// Variable definitions with descriptions
const contextVariables = [
  { key: '{{date}}', description: '当前日期，格式：YYYY-MM-DD' },
  { key: '{{week_start}}', description: '本周开始日期' },
  { key: '{{week_end}}', description: '本周结束日期' },
  { key: '{{generated_at}}', description: '报告生成时间' },
  { key: '{{week_number}}', description: '年内周序号' },
  { key: '{{github_count}}', description: 'GitHub 项目总数' },
  { key: '{{app_name}}', description: '应用名称：AI News Bot' },
]

const githubVariables = [
  { key: '{{github.full_name}}', description: '项目全名 (owner/repo)' },
  { key: '{{github.url}}', description: '项目 URL 地址' },
  { key: '{{github.stars}}', description: '星标数量' },
  { key: '{{github.stars_today}}', description: '今日新增星标' },
  { key: '{{github.language}}', description: '主要编程语言' },
  { key: '{{github.description}}', description: '项目描述' },
  { key: '{{github.index}}', description: '序号 (从 1 开始)' },
]

const articleVariables = [
  { key: '{{article.title}}', description: '文章标题' },
  { key: '{{article.url}}', description: '文章 URL 地址' },
  { key: '{{article.score}}', description: 'AI 评分 (0-100)' },
  { key: '{{article.summary}}', description: 'AI 生成的摘要' },
  { key: '{{article.tags}}', description: '文章标签 (逗号分隔)' },
  { key: '{{article.source_name}}', description: '文章来源名称' },
  { key: '{{article.index}}', description: '序号 (从 1 开始)' },
]

// Load templates on mount
onMounted(async () => {
  await loadPresetTemplates()
  await loadWebhooks()
  if (props.visible) {
    await loadTemplates()
  }
})

// Watch for dialog open
watch(() => props.visible, async (newVal) => {
  if (newVal) {
    await loadTemplates()
    await loadPresetTemplates()
  }
})

// Watch for type change
watch(currentType, async () => {
  await loadTemplates()
})

// Watch for template changes
watch(currentTemplate, () => {
  hasUnsavedChanges.value = true
  validateTemplate(currentTemplate.value)
})

// Load preset templates
async function loadPresetTemplates() {
  try {
    const data = await request.get<{ items: PresetTemplate[] }>('/templates/presets')
    presetTemplates.value = data.items || []
  } catch (e) {
    console.error('Failed to load preset templates:', e)
  }
}

// Load webhooks for copy dialog
async function loadWebhooks() {
  try {
    const data = await request.get<{ items: Webhook[] }>('/webhooks/')
    webhookList.value = (data.items || []).filter((w: Webhook) => w.id !== props.webhookId)
  } catch (e) {
    console.error('Failed to load webhooks:', e)
  }
}

// Load templates for current webhook
async function loadTemplates() {
  try {
    const data = await request.get<{ items: Template[] }>(`/webhooks/${props.webhookId}/templates`)
    const templates = data.items || []

    // Find template for current type
    const template = templates.find((t: Template) => t.template_type === currentType.value)

    if (template) {
      currentTemplate.value = template.template_content
      currentTemplateId.value = template.id || null
      templateName.value = template.template_name
    } else {
      // Use default template for this type
      currentTemplate.value = getDefaultTemplate(currentType.value)
      currentTemplateId.value = null
      templateName.value = `${currentType.value} 模板`
    }

    hasUnsavedChanges.value = false
  } catch (e) {
    console.error('Failed to load templates:', e)
    // Use default
    currentTemplate.value = getDefaultTemplate(currentType.value)
  }
}

// Get default template by type
function getDefaultTemplate(type: string): string {
  const defaults: Record<string, string> = {
    daily: '# 📊 AI资讯日报 - {{date}}\n\n## GitHub 热门\n\n{{#github_loop}}\n{{github.index}}. [{{github.full_name}}]({{github.url}}) - ⭐ {{github.stars}}\n{{github.description}}\n{{/github_loop}}\n\n## 文章精选\n\n{{#article_loop}}\n### {{article.title}}\n评分: {{article.score}} | {{article.tags}}\n\n{{article.summary}}\n{{/article_loop}}',
    weekly: '# 📈 AI资讯周报\n\n{{week_start}} ~ {{week_end}}\n\n## GitHub Trending\n\n{{#github_loop}}\n{{github.index}}. [{{github.full_name}}]({{github.url}}) - ⭐ {{github.stars}}\n{{/github_loop}}\n\n## 精选文章\n\n{{#article_loop}}\n### {{article.title}}\n{{article.summary}}\n{{/article_loop}}',
    immediate: '# {{article.title}}\n\n评分: {{article.score}}\n\n{{article.summary}}\n\n来源: {{article.source_name}}\n\n[查看原文]({{article.url}})'
  }
  return defaults[type] || defaults.daily
}

// Validate template
async function validateTemplate(content: string) {
  if (!content.trim()) {
    validationErrors.value = []
    return
  }

  try {
    const data = await request.post<ValidationResult>('/templates/validate', {
      template_content: content
    })

    if (data.valid) {
      validationErrors.value = []
    } else {
      validationErrors.value = data.errors || []
    }
  } catch (e) {
    console.error('Validation failed:', e)
  }
}

// Template operations
function handleTypeChange() {
  loadTemplates()
}

function handleInsertVariable(variable: string) {
  canvasRef.value?.insertAtCursor(variable)
}

function handleInsertLoop(loopType: string) {
  const loopBlock = `{{#${loopType}}}\n\n{{/${loopType}}}`
  canvasRef.value?.insertAtCursor(loopBlock)
}

function handleRemoveLoop(loopBlock: string) {
  ElMessageBox.confirm('确定要删除这个循环块吗？', '提示', {
    type: 'warning'
  }).then(() => {
    currentTemplate.value = currentTemplate.value.replace(loopBlock, '')
  }).catch(() => {})
}

function handleTemplateChange(content: string) {
  currentTemplate.value = content
}

function handleLoadPreset(presetKey: string) {
  const preset = presetTemplates.value.find((p: PresetTemplate) => p.key === presetKey)
  if (preset) {
    ElMessageBox.confirm(
      `确定要加载预设模板「${preset.name}」吗？这将覆盖当前内容。`,
      '加载预设模板',
      { type: 'warning' }
    ).then(() => {
      currentTemplate.value = preset.content
      templateName.value = preset.name
    }).catch(() => {})
  }
}

function handleImport() {
  importContent.value = ''
  importDialogVisible.value = true
}

function confirmImport() {
  try {
    const parsed = JSON.parse(importContent.value)
    if (parsed.template_content) {
      currentTemplate.value = parsed.template_content
      templateName.value = parsed.template_name || '导入模板'
      importDialogVisible.value = false
      ElMessage.success('模板导入成功')
    } else {
      ElMessage.error('无效的模板格式')
    }
  } catch (e) {
    ElMessage.error('JSON 解析失败，请检查格式')
  }
}

function handleExport() {
  const exportData = {
    template_type: currentType.value,
    template_name: templateName.value,
    template_content: currentTemplate.value
  }

  const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `template-${currentType.value}-${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(url)
}

function handleCopyToOther() {
  if (!currentTemplateId.value) {
    ElMessage.warning('请先保存模板后再复制')
    return
  }
  targetWebhookId.value = null
  copyDialogVisible.value = true
}

async function confirmCopy() {
  if (!targetWebhookId.value) {
    ElMessage.warning('请选择目标 Webhook')
    return
  }

  copying.value = true
  try {
    await request.post('/templates/copy', {
      template_id: currentTemplateId.value,
      target_webhook_id: targetWebhookId.value
    })
    ElMessage.success('模板复制成功')
    copyDialogVisible.value = false
  } catch (e: any) {
    ElMessage.error(e.message || '复制失败')
  } finally {
    copying.value = false
  }
}

async function handleSave() {
  if (!currentTemplate.value.trim()) {
    ElMessage.warning('模板内容不能为空')
    return
  }

  saving.value = true
  try {
    const payload = {
      webhook_id: props.webhookId,
      template_type: currentType.value,
      template_name: templateName.value || `${currentType.value} 模板`,
      template_content: currentTemplate.value,
      is_active: true
    }

    if (currentTemplateId.value) {
      await request.put(`/templates/${currentTemplateId.value}`, payload)
      ElMessage.success('模板已更新')
    } else {
      const result = await request.post<{ id: number }>('/templates', payload)
      currentTemplateId.value = result.id
      ElMessage.success('模板已创建')
    }

    hasUnsavedChanges.value = false
    emit('saved')
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete() {
  if (!currentTemplateId.value) return

  try {
    await ElMessageBox.confirm(
      '确定要删除这个模板吗？删除后将使用系统默认模板。',
      '删除模板',
      { type: 'warning' }
    )

    await request.delete(`/templates/${currentTemplateId.value}`)
    ElMessage.success('模板已删除')

    currentTemplateId.value = null
    currentTemplate.value = getDefaultTemplate(currentType.value)

    emit('saved')
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e.message || '删除失败')
    }
  }
}

// 关闭按钮点击时，有未保存更改则弹窗确认
async function handleDialogClose() {
  if (hasUnsavedChanges.value) {
    try {
      await ElMessageBox.confirm('还有未保存的更改，确定要关闭吗？', '提示', {
        type: 'warning',
        confirmButtonText: '确定',
        cancelButtonText: '取消'
      })
      dialogVisible.value = false
    } catch (e) {
      return // 用户取消，不关闭
    }
  } else {
    dialogVisible.value = false
  }
}
</script>

<style scoped>
/* 整体布局 - 单列 */
.editor-layout {
  display: flex;
  flex-direction: column;
  height: 100%;
  gap: 0;
}

/* 顶部工具栏 */
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: var(--el-fill-color-light);
  border-bottom: 1px solid var(--el-border-color);
  flex-wrap: wrap;
  gap: 12px;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.toolbar-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.toolbar-right {
  display: flex;
  gap: 8px;
}

/* 循环块工具 */
.loop-tools {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  background: var(--el-fill-color);
  border-bottom: 1px solid var(--el-border-color);
  flex-wrap: wrap;
}

.tools-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

/* 变量选择面板 - 横向排列 */
.variable-panel {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color);
  flex-wrap: wrap;
  overflow-x: auto;
}

.panel-section {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.section-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}

.var-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.var-tag {
  cursor: pointer;
  font-size: 11px;
  font-family: 'SF Mono', Monaco, monospace;
  color: var(--el-text-color-primary);
  background: var(--el-fill-color-dark);
  border: 1px solid var(--el-border-color);
  padding: 4px 8px;
  border-radius: 4px;
  transition: all 0.2s;
}

.var-tag:hover {
  background: var(--el-fill-color);
  border-color: var(--el-color-primary);
}

.var-tag.github {
  background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
  color: #ffffff;
  border: none;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
}

.var-tag.github:hover {
  filter: brightness(1.1);
  box-shadow: 0 2px 8px rgba(17, 153, 142, 0.4);
}

.var-tag.article {
  background: linear-gradient(135deg, #fc4a1a 0%, #f7b733 100%);
  color: #ffffff;
  border: none;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
}

.var-tag.article:hover {
  filter: brightness(1.1);
  box-shadow: 0 2px 8px rgba(252, 74, 26, 0.4);
}

/* 模板编辑器 */
.template-editor-wrapper {
  flex: 1;
  min-height: 300px;
  display: flex;
  flex-direction: column;
}

/* 预设选项 */
.preset-option {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.preset-name {
  font-weight: 500;
}

.preset-desc {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

/* 响应式布局 */
@media screen and (max-width: 1200px) {
  .toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .toolbar-left,
  .toolbar-right {
    justify-content: center;
    flex-wrap: wrap;
  }

  .variable-panel {
    flex-direction: column;
    align-items: flex-start;
  }

  .panel-section {
    width: 100%;
  }

  .el-divider {
    display: none;
  }
}

@media screen and (max-width: 768px) {
  .loop-tools {
    flex-direction: column;
    align-items: stretch;
  }

  .loop-tools .el-button {
    width: 100%;
  }
}
</style>
