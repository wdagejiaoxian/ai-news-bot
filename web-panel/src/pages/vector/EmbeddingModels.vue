<template>
  <div class="embedding-models-page">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>Embedding 模型管理</span>
          <el-button type="primary" size="small" @click="showCreateDialog">
            <el-icon><Plus /></el-icon>
            注册模型
          </el-button>
        </div>
      </template>

      <el-table v-loading="loading" :data="models" stripe style="width: 100%">
        <el-table-column prop="display_name" label="名称" min-width="160" />
        <el-table-column prop="provider" label="提供商" width="130" align="center">
          <template #default="{ row }">
            <el-tag size="small">{{ getProviderName(row.provider) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="model_name" label="模型" min-width="200">
          <template #default="{ row }">
            <span class="cell-text">{{ row.model_name }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="dimension" label="维度" width="80" align="center" />
        <!-- 新增：维度兼容列 -->
        <el-table-column label="维度兼容" width="200" align="center">
          <template #default="{ row }">
            <template v-if="activeDimension === null">
              <el-tag type="warning" effect="plain">
                <el-icon><WarningFilled /></el-icon>
                待配置向量库
              </el-tag>
            </template>
            <template v-else-if="row.dimension === activeDimension">
              <el-tag type="success" effect="plain">
                <el-icon><Check /></el-icon>
                兼容 ({{ activeDimension }})
              </el-tag>
            </template>
            <template v-else>
              <el-tooltip
                :content="`模型维度 ${row.dimension} ≠ 当前配置 ${activeDimension}。建议切换配置或使用兼容模型。`"
                placement="top"
              >
                <el-tag type="info" effect="plain">
                  <el-icon><Close /></el-icon>
                  不兼容 ({{ row.dimension }})
                </el-tag>
              </el-tooltip>
            </template>
          </template>
        </el-table-column>
        <el-table-column prop="max_concurrency" label="并发" width="70" align="center" />
        <el-table-column prop="priority" label="优先级" width="80" align="center" />
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_enabled ? 'success' : 'danger'" size="small">
              {{ row.is_enabled ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right" align="center">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button type="primary" link size="small" @click="handleTest(row)">
                测试
              </el-button>
              <el-button type="primary" link size="small" @click="showEditDialog(row)">
                编辑
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

      <div v-if="!loading && models.length === 0" class="empty-state">
        <div class="empty-state__icon">
          <el-icon :size="32"><Connection /></el-icon>
        </div>
        <div class="empty-state__title">暂无 Embedding 模型</div>
        <div class="empty-state__desc">
          点击上方"注册模型"创建您的第一个 Embedding 模型配置。
          <br>
          <span class="empty-state__hint">
            配置 Embedding 模型后，即可使用语义搜索、文章去重、相似推荐等向量功能。
          </span>
        </div>
      </div>
    </el-card>

    <!-- 创建/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEditing ? '编辑模型' : '注册模型'"
      width="520px"
    >
      <el-form ref="formRef" :model="formData" label-width="100px">
        <el-form-item label="显示名称" prop="display_name">
          <el-input v-model="formData.display_name" placeholder="Web 面板显示名称" />
        </el-form-item>
        <el-form-item label="提供商" prop="provider">
          <el-select v-model="formData.provider" placeholder="选择提供商" style="width: 100%;">
            <el-option label="Ollama (本地)" value="ollama" />
            <el-option label="OpenAI" value="openai" />
            <el-option label="硅基流动" value="siliconflow" />
            <el-option label="OpenRouter" value="openrouter" />
          </el-select>
        </el-form-item>
        <el-form-item label="模型名" prop="model_name">
          <el-input v-model="formData.model_name" placeholder="如 nomic-embed-text" />
        </el-form-item>
        <el-form-item label="API Key" :prop="isEditing ? '' : 'api_key'" :rules="isEditing ? [] : [{ required: true, message: '请填写 API Key', trigger: 'blur' }]">
          <el-input
            v-model="formData.api_key"
            type="password"
            show-password
            :placeholder="isEditing ? '不修改请留空' : 'Ollama 可留空'"
          />
        </el-form-item>
        <el-form-item label="API Base">
          <el-input v-model="formData.api_base" placeholder="默认使用标准地址，留空即可" />
        </el-form-item>
        <el-form-item label="向量维度" prop="dimension">
          <el-input-number v-model="formData.dimension" :min="1" :max="65536" placeholder="模型输出的向量维度" />
          <div class="form-tip">不同模型输出维度不同，如 nomic-embed-text=768, bge-large-zh-v1.5=1024</div>
        </el-form-item>
        <el-form-item label="最大批量">
          <el-input-number v-model="formData.max_batch_size" :min="1" :max="100" />
          <div class="form-tip">单次请求最大文本数量</div>
        </el-form-item>
        <el-form-item label="并发数">
          <el-input-number v-model="formData.max_concurrency" :min="1" :max="20" />
        </el-form-item>
        <el-form-item label="优先级">
          <el-input-number v-model="formData.priority" :min="1" :max="100" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="formData.is_enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 测试结果弹窗 -->
    <el-dialog v-model="testDialogVisible" title="连通性测试" width="400px">
      <el-result
        :icon="testResult.success ? 'success' : 'error'"
        :title="testResult.success ? '测试成功' : '测试失败'"
      >
        <template #sub-title>
          {{ testResult.message }}
        </template>
      </el-result>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance } from 'element-plus'
import { Plus, Connection, WarningFilled, Check, Close } from '@element-plus/icons-vue'
import {
  getEmbeddingModels,
  createEmbeddingModel,
  updateEmbeddingModel,
  deleteEmbeddingModel,
  testEmbeddingModel,
  getEmbeddingHealth,
} from '@/api/vector'
import type { EmbeddingModel, EmbeddingHealth } from '@/types/vector'

const loading = ref(false)
const saving = ref(false)
const models = ref<EmbeddingModel[]>([])
const dialogVisible = ref(false)
const testDialogVisible = ref(false)
const isEditing = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const activeDimension = ref<number | null>(null) // 从 health API 获取

const testResult = reactive({
  success: false,
  message: '',
})

// 表单验证规则
const rules = {
  model_name: [
    { required: true, message: '请填写模型名称', trigger: 'blur' },
  ],
  provider: [
    { required: true, message: '请选择提供商', trigger: 'change' },
  ],
}

const providerNames: Record<string, string> = {
  ollama: 'Ollama (本地)',
  openai: 'OpenAI',
  siliconflow: '硅基流动',
  openrouter: 'OpenRouter',
}

const getProviderName = (provider: string) => providerNames[provider] || provider

const formData = reactive({
  display_name: '',
  provider: 'ollama',
  model_name: '',
  api_key: '',
  api_base: '',
  dimension: 768,
  max_batch_size: 20,
  max_concurrency: 3,
  priority: 10,
  is_enabled: true,
})

const fetchModels = async () => {
  loading.value = true
  try {
    const res = await getEmbeddingModels()
    models.value = res.models || []
  } catch (e: any) {
    ElMessage.error(e?.message || '获取模型列表失败')
  } finally {
    loading.value = false
  }
}

const fetchActiveDimension = async () => {
  try {
    const res = await getEmbeddingHealth()
    activeDimension.value = res.active_dimension ?? null
  } catch {
    activeDimension.value = null
  }
}

const resetForm = () => {
  formData.display_name = ''
  formData.provider = 'ollama'
  formData.model_name = ''
  formData.api_key = ''
  formData.api_base = ''
  formData.dimension = 768
  formData.max_batch_size = 20
  formData.max_concurrency = 3
  formData.priority = 10
  formData.is_enabled = true
}

const showCreateDialog = () => {
  isEditing.value = false
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

const showEditDialog = (model: EmbeddingModel) => {
  isEditing.value = true
  editingId.value = model.id
  formData.display_name = model.display_name
  formData.provider = model.provider
  formData.model_name = model.model_name
  formData.api_key = ''
  formData.api_base = model.api_base || ''
  formData.dimension = model.dimension || 768
  formData.max_batch_size = model.max_batch_size || 20
  formData.max_concurrency = model.max_concurrency
  formData.priority = model.priority
  formData.is_enabled = model.is_enabled
  dialogVisible.value = true
}

const handleSubmit = async () => {
  if (!formRef.value) return

  // 创建时验证 api_key
  if (!isEditing.value && !formData.api_key) {
    ElMessage.warning('请填写 API Key')
    return
  }

  try {
    await formRef.value.validate()
  } catch {
    return
  }

  saving.value = true
  try {
    const payload = {
      display_name: formData.display_name || formData.model_name,
      provider: formData.provider,
      model_name: formData.model_name,
      api_key: formData.api_key || undefined,
      api_base: formData.api_base || undefined,
      dimension: formData.dimension,
      max_batch_size: formData.max_batch_size,
      max_concurrency: formData.max_concurrency,
      priority: formData.priority,
      is_enabled: formData.is_enabled,
    }

    if (isEditing.value && editingId.value) {
      const res = await updateEmbeddingModel(editingId.value, payload)
      // 处理后端返回的维度调整提示
      if (res?.dimension_warning) {
        ElMessage.warning(res.dimension_warning)
      } else {
        ElMessage.success('模型更新成功')
      }
    } else {
      const res = await createEmbeddingModel(payload)
      // Task 9: 处理后端返回的维度调整提示
      if (res?.dimension_warning) {
        ElMessage.warning(res.dimension_warning)
      } else {
        ElMessage.success('模型注册成功')
      }
    }
    dialogVisible.value = false
    fetchModels()
  } catch (e: any) {
    ElMessage.error(e?.message || '操作失败')
  } finally {
    saving.value = false
  }
}

const handleDelete = async (model: EmbeddingModel) => {
  try {
    await deleteEmbeddingModel(model.id)
    ElMessage.success('模型已删除')
    fetchModels()
  } catch (e: any) {
    ElMessage.error(e?.message || '删除失败')
  }
}

const handleTest = async (model: EmbeddingModel) => {
  testResult.success = false
  testResult.message = ''
  testDialogVisible.value = true
  try {
    const res = await testEmbeddingModel(model.id)
    testResult.success = res.healthy ?? false
    testResult.message = res.message || (res.healthy ? '连通性正常' : '连通性异常')
  } catch (e: any) {
    testResult.success = false
    testResult.message = e?.message || '测试失败，请检查配置'
  }
}

onMounted(async () => {
  await fetchModels()
  await fetchActiveDimension()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.cell-text {
  word-break: break-word;
}

.action-buttons {
  display: flex;
  justify-content: center;
  gap: 4px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 0;
  color: #909399;
}

.empty-state__icon {
  margin-bottom: 12px;
}

.empty-state__title {
  font-size: 16px;
  font-weight: 500;
  margin-bottom: 8px;
}

.empty-state__desc {
  font-size: 14px;
}

.empty-state__hint {
  font-size: 12px;
  color: var(--el-color-info);
  margin-top: 8px;
  display: inline-block;
}
</style>
