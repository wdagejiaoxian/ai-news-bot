<template>
  <div class="vectordb-config-page">
    <!-- 状态概览卡片 -->
    <el-row :gutter="16" class="overview-cards">
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>
            <span>当前激活配置</span>
          </template>
          <div v-if="activeConfig" class="active-config-info">
            <el-descriptions :column="2" border size="small">
              <el-descriptions-item label="数据库">
                <el-tag size="small">{{ activeConfig.db_type }}</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="维度">
                <el-tag type="success" size="small">{{ activeConfig.dimension }}</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="Articles Collection" :span="2">
                <code class="config-code">{{ activeConfig.collection_names?.articles }}</code>
              </el-descriptions-item>
              <el-descriptions-item label="文章向量">
                {{ activeConfig.articles_count ?? 0 }}
              </el-descriptions-item>
              <el-descriptions-item label="GitHub 向量">
                {{ activeConfig.github_count ?? 0 }}
              </el-descriptions-item>
            </el-descriptions>
          </div>
          <div v-else class="empty-hint">暂无激活配置</div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>
            <span>Embedding 系统状态</span>
          </template>
          <div v-if="embeddingHealth" class="health-info">
            <el-descriptions :column="2" border size="small">
              <el-descriptions-item label="可用性">
                <el-tag :type="embeddingHealth.available ? 'success' : 'danger'" size="small">
                  {{ embeddingHealth.available ? '在线' : '离线' }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="可用模型">
                {{ embeddingHealth.active_models }}
              </el-descriptions-item>
              <el-descriptions-item label="当前维度">
                {{ embeddingHealth.active_dimension ?? '未配置' }}
              </el-descriptions-item>
              <el-descriptions-item label="兼容模型">
                <el-tag type="success" size="small">
                  {{ embeddingHealth.models_compatibility?.compatible_count ?? 0 }}
                </el-tag>
                /
                <el-tag type="info" size="small">
                  {{ embeddingHealth.models_compatibility?.incompatible_count ?? 0 }}
                </el-tag>
              </el-descriptions-item>
            </el-descriptions>
          </div>
          <div v-else class="empty-hint">加载中...</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 配置列表 -->
    <el-card shadow="never" class="config-list-card">
      <template #header>
        <div class="card-header">
          <span>配置列表</span>
          <el-button type="primary" size="small" @click="showAddDialog" :loading="loading">
            <el-icon><Plus /></el-icon>
            新增配置
          </el-button>
        </div>
      </template>

      <el-table
        v-loading="loading"
        :data="configs"
        stripe
        style="width: 100%"
        :row-class-name="tableRowClassName"
        highlight-current-row
      >
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="db_type" label="数据库" width="100">
          <template #default="{ row }">
            <el-tag size="small">{{ row.db_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="dimension" label="维度" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.dimension }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="collection_names.articles" label="Articles Collection" min-width="280">
          <template #default="{ row }">
            <code class="collection-name">{{ row.collection_names?.articles }}</code>
          </template>
        </el-table-column>
        <el-table-column prop="articles_count" label="文章向量" width="100" align="center" />
        <el-table-column label="状态" width="150">
          <template #default="{ row }">
            <div class="status-tags">
              <el-tag v-if="row.is_active" type="success" size="small">当前激活</el-tag>
              <el-tag v-if="row.is_default" type="warning" size="small">默认配置</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right" align="center">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button
                v-if="!row.is_active"
                type="primary"
                link
                size="small"
                @click="handleActivate(row)"
              >
                激活
              </el-button>
              <el-tooltip
                :content="row.is_default ? '默认配置不支持删除' : row.is_active ? '请先切换到其他配置' : '删除此配置'"
                :disabled="!row.is_default && !row.is_active"
                placement="top"
              >
                <el-button
                  type="danger"
                  link
                  size="small"
                  :disabled="row.is_default || row.is_active"
                  @click="handleDelete(row)"
                >
                  删除
                </el-button>
              </el-tooltip>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="!loading && configs.length === 0" class="empty-state">
        <div class="empty-state__icon">
          <el-icon :size="32"><Connection /></el-icon>
        </div>
        <div class="empty-state__title">暂无向量数据库配置</div>
        <div class="empty-state__desc">点击"新增配置"创建您的第一个向量数据库配置</div>
      </div>
    </el-card>

    <!-- 新增配置弹窗 -->
    <el-dialog v-model="addDialogVisible" title="新增向量数据库配置" width="480px">
      <el-form ref="addFormRef" :model="addFormData" label-width="120px">
        <el-form-item label="数据库类型" prop="db_type">
          <el-select v-model="addFormData.db_type" disabled style="width: 100%;">
            <el-option label="ChromaDB（当前仅支持）" value="chromadb" />
          </el-select>
        </el-form-item>
        <el-form-item label="连接字符串" prop="connection_string">
          <el-input v-model="addFormData.connection_string" placeholder="storage/chromadb" />
          <div class="form-tip">ChromaDB 使用本地路径作为存储目录</div>
        </el-form-item>
        <el-form-item label="向量维度" prop="dimension">
          <el-input-number
            v-model="addFormData.dimension"
            :min="1"
            :max="65536"
            placeholder="向量维度，必须 > 0"
            style="width: 100%;"
          />
          <div class="form-tip">需与 Embedding 模型的 dimension 匹配</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleAddSubmit">创建配置</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance } from 'element-plus'
import { Plus, Connection } from '@element-plus/icons-vue'
import {
  getVectorDBConfigs,
  createVectorDBConfig,
  activateVectorDBConfig,
  deleteVectorDBConfig,
  getEmbeddingHealth,
} from '@/api/vector'
import type {
  VectorDBConfigFull,
  EmbeddingHealth,
} from '@/types/vector'

const loading = ref(false)
const saving = ref(false)
const configs = ref<VectorDBConfigFull[]>([])
const embeddingHealth = ref<EmbeddingHealth | null>(null)
const addDialogVisible = ref(false)
const addFormRef = ref<FormInstance>()

const activeConfig = computed(() => configs.value.find(c => c.is_active) || null)

const addFormData = reactive({
  db_type: 'chromadb',
  connection_string: 'storage/chromadb',
  dimension: 1024,
})

const tableRowClassName = ({ row }: { row: VectorDBConfigFull }) => {
  return row.is_active ? 'active-row' : ''
}

const fetchConfigs = async () => {
  loading.value = true
  try {
    const res = await getVectorDBConfigs()
    configs.value = res.configs || []
  } catch (e: any) {
    ElMessage.error(e?.message || '获取配置列表失败')
  } finally {
    loading.value = false
  }
}

const fetchEmbeddingHealth = async () => {
  try {
    const res = await getEmbeddingHealth()
    embeddingHealth.value = res
  } catch {
    embeddingHealth.value = null
  }
}

const showAddDialog = () => {
  addFormData.db_type = 'chromadb'
  addFormData.connection_string = 'storage/chromadb'
  addFormData.dimension = 1024
  addDialogVisible.value = true
}

const handleAddSubmit = async () => {
  if (!addFormRef.value) return

  try {
    await addFormRef.value.validate()
  } catch {
    return
  }

  if (addFormData.dimension <= 0) {
    ElMessage.warning('维度必须大于 0')
    return
  }

  saving.value = true
  try {
    await createVectorDBConfig({
      db_type: addFormData.db_type,
      connection_string: addFormData.connection_string,
      dimension: addFormData.dimension,
    })
    ElMessage.success('配置已创建')
    addDialogVisible.value = false
    await fetchConfigs()
    await fetchEmbeddingHealth()
  } catch (e: any) {
    ElMessage.error(e?.message || '创建失败')
  } finally {
    saving.value = false
  }
}

const handleActivate = async (row: VectorDBConfigFull) => {
  try {
    await ElMessageBox.confirm(
      `切换后，向量维度将变为 ${row.dimension}。维度不匹配的 Embedding 模型将被禁用。是否继续？`,
      '确认切换',
      {
        confirmButtonText: '确认切换',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
  } catch {
    return // 用户取消
  }

  loading.value = true
  try {
    await activateVectorDBConfig(row.id)
    ElMessage.success(`已切换到配置 id=${row.id}，维度 ${row.dimension}`)
    await fetchConfigs()
    await fetchEmbeddingHealth()
  } catch (e: any) {
    ElMessage.error(e?.message || '激活失败')
  } finally {
    loading.value = false
  }
}

const handleDelete = async (row: VectorDBConfigFull) => {
  try {
    await ElMessageBox.confirm(
      `删除配置将同时删除 ChromaDB 中的向量数据（${row.collection_names?.articles} 和 ${row.collection_names?.github_repos}），数据不可恢复。是否继续？`,
      '确认删除',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
  } catch {
    return // 用户取消
  }

  loading.value = true
  try {
    const res = await deleteVectorDBConfig(row.id)
    ElMessage.success(`配置 id=${row.id} 已删除`)
    await fetchConfigs()
    await fetchEmbeddingHealth()
  } catch (e: any) {
    ElMessage.error(e?.message || '删除失败')
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await fetchConfigs()
  await fetchEmbeddingHealth()
})
</script>

<style scoped>
.overview-cards {
  margin-bottom: 16px;
}

.active-config-info .config-code,
.collection-name {
  font-family: 'Courier New', monospace;
  font-size: 12px;
  background: #f5f7fa;
  padding: 2px 6px;
  border-radius: 4px;
  word-break: break-all;
}

.empty-hint {
  color: #909399;
  font-size: 14px;
  padding: 8px 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.status-tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
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

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
  line-height: 1.4;
}

:deep(.active-row) {
  background-color: #f0f9eb !important;
}
</style>