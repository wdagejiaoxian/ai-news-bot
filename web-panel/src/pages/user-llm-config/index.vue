<template>
  <div class="user-llm-config-page">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>我的LLM配置</span>
          <el-button type="primary" size="small" @click="handleAdd">
            <el-icon><Plus /></el-icon>
            添加配置
          </el-button>
        </div>
      </template>

      <!-- 配置列表 -->
      <el-table v-loading="loading" :data="configs" style="width: 100%">
        <el-table-column prop="provider" label="平台" width="140" align="center">
          <template #default="{ row }">
            <el-tag size="small">{{ getProviderName(row.provider) }}</el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="model_name" label="模型" min-width="180">
          <template #default="{ row }">
            <span class="cell-text">{{ row.model_name }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="api_base" label="API地址" min-width="230">
          <template #default="{ row }">
            <span class="cell-text">{{ row.api_base || '-' }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="max_concurrent" label="并发" width="80" align="center" />

        <el-table-column label="工具调用" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.can_use_tool ? 'success' : 'info'" size="small">
              {{ row.can_use_tool ? '支持' : '不支持' }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="is_active" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="180" fixed="right" align="center">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button type="primary" link size="small" @click="handleEdit(row)">
                编辑
              </el-button>
              <el-button type="success" link size="small" @click="handleTest(row)">
                测试
              </el-button>
              <el-popconfirm title="确定删除?" @confirm="handleDelete(row)">
                <template #reference>
                  <el-button type="danger" link size="small">删除</el-button>
                </template>
              </el-popconfirm>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <!-- 空状态 -->
      <div v-if="!loading && configs.length === 0" class="empty-state">
        <div class="empty-state__icon">
          <el-icon :size="32"><Cpu /></el-icon>
        </div>
        <div class="empty-state__title">暂无 LLM 配置</div>
        <div class="empty-state__desc">点击上方"添加配置"创建您的第一个 LLM 配置</div>
      </div>
    </el-card>

    <!-- 添加/编辑弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑LLM配置' : '添加LLM配置'"
      width="600px"
    >
      <el-form ref="formRef" :model="form" :rules="effectiveRules" label-width="100px">
        <el-form-item label="平台" prop="provider">
<!--          <el-select-->
<!--            v-model="form.provider"-->
<!--            placeholder="选择平台"-->
<!--            style="width: 100%;"-->
<!--            :disabled="isEdit"-->
<!--            @change="onPlatformChange"-->
<!--          >-->
          <el-select
            v-model="form.provider"
            placeholder="选择平台"
            style="width: 100%;"
            @change="onPlatformChange"
          >
            <el-option
              v-for="p in platformOptions"
              :key="p.platform"
              :label="p.name"
              :value="p.platform"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="模型" prop="model_name">
          <el-select
            v-model="form.model_name"
            filterable
            allow-create
            default-first-option
            placeholder="选择或输入模型名称"
            style="width: 100%;"
          >
            <el-option
              v-for="m in availableModels"
              :key="m"
              :label="m"
              :value="m"
            />
          </el-select>
          <div class="form-tip">
            如需添加多个模型，请分别创建配置
          </div>
        </el-form-item>

        <el-form-item label="API Key" prop="api_key">
          <el-input
            v-model="form.api_key"
            type="password"
            show-password
            :placeholder="isEdit ? '不修改请留空' : '请输入API Key'"
          />
        </el-form-item>

        <el-form-item label="API Base" prop="api_base">
          <el-input v-model="form.api_base" placeholder="留空使用平台默认值" />
        </el-form-item>

        <el-form-item label="并发数" prop="max_concurrent">
          <el-input-number v-model="form.max_concurrent" :min="1" :max="10" />
        </el-form-item>

        <el-form-item label="启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">
          保存
        </el-button>
      </template>
    </el-dialog>

    <!-- 测试结果弹窗 -->
    <el-dialog v-model="testDialogVisible" title="测试结果" width="400px">
      <el-result
        :icon="testResult.success ? 'success' : 'error'"
        :title="testResult.success ? '测试成功' : '测试失败'"
      >
        <template #sub-title>
          {{ testResult.message }}
          <div v-if="testResult.model_used" class="test-model">
            使用模型: {{ testResult.model_used }}
          </div>
        </template>
      </el-result>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { request } from '@/api'

interface UserLLMConfig {
  id: number
  provider: string
  api_key: string
  api_base: string
  model_name: string
  is_active: boolean
  max_concurrent: number
  can_use_tool: boolean
}

interface PlatformOption {
  platform: string
  name: string
  api_base: string
  models: string[]
}

const formRef = ref<FormInstance>()
const loading = ref(false)
const saving = ref(false)
const configs = ref<UserLLMConfig[]>([])
const platformOptions = ref<PlatformOption[]>([])

const dialogVisible = ref(false)
const testDialogVisible = ref(false)
const isEdit = ref(false)
const editingId = ref<number | null>(null)
// 保存编辑前的原始数据，用于对比变更
const originalData = ref<{
  provider: string
  model_name: string
  api_base: string
  max_concurrent: number
  is_active: boolean
} | null>(null)

const form = reactive({
  provider: '',
  model_name: '',
  api_key: '',
  api_base: '',
  max_concurrent: 1,
  is_active: true,
})

const testResult = reactive({
  success: false,
  message: '',
  model_used: '',
})

// 动态验证规则：编辑模式下 api_key 非必填
const effectiveRules = computed<FormRules>(() => {
  const baseRules: FormRules = {
    provider: [{ required: true, message: '请选择平台', trigger: 'change' }],
    model_name: [{ required: true, message: '请选择或输入模型', trigger: 'change' }],
  }
  // 编辑模式下 api_key 非必填（因为不想改就不传）
  if (isEdit.value) {
    // 编辑模式：api_key 完全非必填
    return baseRules
  } else {
    // 新增模式：api_key 必填
    return {
      ...baseRules,
      api_key: [{ required: true, message: '请输入API Key', trigger: 'blur' }],
    }
  }
})

const availableModels = computed(() => {
  const p = platformOptions.value.find(p => p.platform === form.provider)
  return p?.models || []
})

function getProviderName(platform: string) {
  const p = platformOptions.value.find(p => p.platform === platform)
  return p?.name || platform
}

function onPlatformChange() {
  const p = platformOptions.value.find(p => p.platform === form.provider)
  if (p) {
    form.api_base = p.api_base
    form.model_name = ''
  }
}

async function fetchPlatforms() {
  try {
    const data = await request.get('/models/platforms')
    platformOptions.value = data.platforms || []
  } catch (e) {
    console.error('获取平台列表失败', e)
  }
}

async function fetchConfigs() {
  loading.value = true
  try {
    const data = await request.get('/models/')
    configs.value = data.items || []
  } catch (e) {
    console.error('获取配置失败', e)
  } finally {
    loading.value = false
  }
}

function handleAdd() {
  isEdit.value = false
  editingId.value = null
  form.provider = ''
  form.model_name = ''
  form.api_key = ''
  form.api_base = ''
  form.max_concurrent = 1
  form.is_active = true
  dialogVisible.value = true
}

function handleEdit(row: UserLLMConfig) {
  isEdit.value = true
  editingId.value = row.id
  // 保存原始数据，用于后续对比变更
  originalData.value = {
    provider: row.provider,
    model_name: row.model_name,
    api_base: row.api_base || '',
    max_concurrent: row.max_concurrent,
    is_active: row.is_active,
  }
  form.provider = row.provider
  form.model_name = row.model_name
  form.api_key = ''  // 不回填
  form.api_base = row.api_base || ''
  form.max_concurrent = row.max_concurrent
  form.is_active = row.is_active
  dialogVisible.value = true
}

async function handleSave() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    saving.value = true
    try {
      // 编辑模式：只传递变更的字段
      if (isEdit.value && editingId.value && originalData.value) {
        const payload: Record<string, any> = {}

        // 对比每个字段，只添加变更的字段
        if (form.provider !== originalData.value.provider) {
          payload.provider = form.provider
        }
        if (form.model_name !== originalData.value.model_name) {
          payload.model_name = form.model_name
        }
        if (form.api_base !== originalData.value.api_base) {
          payload.api_base = form.api_base || null  // 空时传 null 让后端清除
        }
        if (form.max_concurrent !== originalData.value.max_concurrent) {
          payload.max_concurrent = form.max_concurrent
        }
        if (form.is_active !== originalData.value.is_active) {
          payload.is_active = form.is_active
        }
        // API Key 单独处理：非空时才算变更
        if (form.api_key.trim() !== '') {
          payload.api_key = form.api_key
        }

        // 如果没有变更，直接提示
        if (Object.keys(payload).length === 0) {
          ElMessage.warning('没有检测到变更，无需保存')
          dialogVisible.value = false
          saving.value = false
          return
        }

        await request.put(`/models/${editingId.value}`, payload)
        ElMessage.success('配置已更新')
      } else {
        // 新增模式：传递所有字段
        const payload = {
          provider: form.provider,
          model_name: form.model_name,
          api_key: form.api_key,
          api_base: form.api_base || undefined,
          max_concurrent: form.max_concurrent,
          is_active: form.is_active,
        }
        await request.post('/models/', payload)
        ElMessage.success('配置已创建')
      }
      
      dialogVisible.value = false
      await fetchConfigs()
    } catch (e: any) {
      ElMessage.error(e.response?.data?.detail || '保存失败')
    } finally {
      saving.value = false
    }
  })
}

async function handleDelete(row: UserLLMConfig) {
  try {
    await request.delete(`/models/${row.id}`)
    ElMessage.success('已删除')
    await fetchConfigs()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

async function handleTest(row: UserLLMConfig) {
  try {
    const data = await request.post(`/models/${row.id}/test`)
    testResult.success = data.success
    testResult.message = data.message
    testResult.model_used = data.model_used || ''
    testDialogVisible.value = true
  } catch (e: any) {
    testResult.success = false
    testResult.message = e.response?.data?.detail || '测试请求失败'
    testResult.model_used = ''
    testDialogVisible.value = true
  }
}

onMounted(async () => {
  await Promise.all([fetchPlatforms(), fetchConfigs()])
})
</script>

<style scoped>
.user-llm-config-page {
  padding: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.model-tag {
  margin-right: var(--spacing-xs);
}

.form-tip {
  font-size: var(--font-size-small);
  color: var(--color-text-muted);
  margin-top: var(--spacing-xs);
}

.test-model {
  margin-top: var(--spacing-sm);
  color: var(--color-primary);
}

/* 单元格文本不截断，支持换行 */
.cell-text {
  display: block;
  width: 100%;
  word-break: break-all;
  white-space: normal;
  line-height: 1.5;
}

/* 操作按钮容器 */
.action-buttons {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: var(--spacing-xs);
  flex-wrap: nowrap;
  min-width: max-content;
}

/* 对话框响应式 */
:deep(.el-dialog) {
  width: 90%;
  max-width: 600px;
  border-radius: var(--radius-lg);
  transition: width var(--transition-duration-normal) var(--transition-timing),
    max-width var(--transition-duration-normal) var(--transition-timing);
}

:deep(.el-dialog__header) {
  padding: var(--spacing-md) var(--spacing-lg);
  border-bottom: 1px solid var(--color-border);
}

:deep(.el-dialog__body) {
  padding: var(--spacing-lg);
}

:deep(.el-dialog__footer) {
  padding: var(--spacing-md) var(--spacing-lg);
  border-top: 1px solid var(--color-border);
}

@media (max-width: 767px) {
  :deep(.el-dialog) {
    width: 95%;
    max-width: none;
  }
}
</style>
