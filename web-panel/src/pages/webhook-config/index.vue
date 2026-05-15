<template>
  <div class="webhook-config-page">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>Webhook配置</span>
          <el-button type="primary" @click="handleAdd">
            <el-icon><Plus /></el-icon>
            添加
          </el-button>
        </div>
      </template>

      <!-- 配置卡片列表 -->
      <div v-loading="loading" class="webhook-card-list">
        <div
          v-for="webhook in webhooks"
          :key="webhook.id"
          class="webhook-card"
        >
          <!-- Webhook 信息 -->
          <div class="webhook-info">
            <div class="webhook-header">
              <div class="webhook-title">
                <el-tag size="small" type="info">{{ webhook.platform.toUpperCase() }}</el-tag>
                <span class="webhook-name">{{ webhook.name }}</span>
              </div>
              <div class="webhook-status">
                <el-tag v-if="webhook.is_disabled" size="small" type="danger">停用</el-tag>
                <el-tag v-else size="small" :type="webhook.is_active ? 'success' : 'info'">
                  {{ webhook.is_active ? '启用' : '禁用' }}
                </el-tag>
                <el-tag v-if="webhook.push_fail_count > 0" size="small" type="warning">
                  失败 {{ webhook.push_fail_count }}/{{ webhook.push_fail_threshold }}
                </el-tag>
              </div>
            </div>

            <div class="webhook-stats">
              <div class="stat-item">
                <span class="stat-label">高分推送</span>
                <el-tag size="small" :type="webhook.push_immediate_enabled ? 'success' : 'info'">
                  {{ webhook.push_immediate_enabled ? '启用' : '禁用' }}
                </el-tag>
                <span class="stat-value">{{ webhook.push_immediate_threshold }}分</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">日报推送</span>
                <el-tag size="small" :type="webhook.push_daily_enabled ? 'success' : 'info'">
                  {{ webhook.push_daily_enabled ? '启用' : '禁用' }}
                </el-tag>
                <span class="stat-value">{{ webhook.push_daily_threshold }}分</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">周报推送</span>
                <el-tag size="small" :type="webhook.push_weekly_enabled ? 'success' : 'info'">
                  {{ webhook.push_weekly_enabled ? '启用' : '禁用' }}
                </el-tag>
                <span class="stat-value">{{ webhook.push_weekly_threshold }}分</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">数量限制</span>
                <span class="stat-value">日{{ webhook.push_daily_limit || '-' }} / 周{{ webhook.push_weekly_limit || '-' }}</span>
              </div>
            </div>
          </div>

          <!-- 分隔线 -->
          <el-divider class="webhook-divider" />

          <!-- 模板快捷入口 -->
          <div class="template-section">
            <div class="template-header">
              <span class="template-title">📝 消息模板</span>
              <el-button type="primary" plain size="small" @click="handleTemplateEdit(webhook)">
                <el-icon><Edit /></el-icon>
                编辑模板
              </el-button>
            </div>
            <div class="template-badges">
              <el-tag
                :type="webhook.templates?.some(t => t.template_type === 'daily') ? 'success' : 'info'"
                size="small"
                class="template-badge"
              >
                日报模板
              </el-tag>
              <el-tag
                :type="webhook.templates?.some(t => t.template_type === 'weekly') ? 'success' : 'info'"
                size="small"
                class="template-badge"
              >
                周报模板
              </el-tag>
              <el-tag
                :type="webhook.templates?.some(t => t.template_type === 'immediate') ? 'success' : 'info'"
                size="small"
                class="template-badge"
              >
                即时推送模板
              </el-tag>
            </div>
          </div>

          <!-- 操作按钮 -->
          <div class="webhook-actions">
            <el-button type="primary" link size="small" @click="handleEdit(webhook)">
              <el-icon><Edit /></el-icon>
              编辑
            </el-button>
            <el-button type="success" link size="small" @click="handleTest(webhook)">
              <el-icon><Bell /></el-icon>
              测试
            </el-button>
            <el-popconfirm title="确定删除?" @confirm="handleDelete(webhook)">
              <template #reference>
                <el-button type="danger" link size="small">
                  <el-icon><Delete /></el-icon>
                  删除
                </el-button>
              </template>
            </el-popconfirm>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-if="!loading && webhooks.length === 0" class="empty-state">
        <div class="empty-state__icon">
          <el-icon :size="32"><Bell /></el-icon>
        </div>
        <div class="empty-state__title">暂无 Webhook 配置</div>
        <div class="empty-state__desc">点击上方"添加"按钮创建您的第一个 Webhook</div>
      </div>
    </el-card>

    <!-- 添加/编辑弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑 Webhook 配置' : '添加 Webhook 配置'"
      width="600px"
      class="webhook-dialog"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="formRules"
        label-width="100px"
        label-position="left"
      >
        <!-- 第一步：基本配置 -->
        <div class="form-section">
          <div class="section-title">
            <span class="step-badge">1</span>
            基本配置
          </div>

          <el-form-item label="配置名称" prop="name">
            <el-input
              v-model="form.name"
              placeholder="给这个配置起个名字"
              maxlength="50"
              show-word-limit
            />
          </el-form-item>

          <el-form-item label="平台" prop="platform">
            <el-select
              v-model="form.platform"
              placeholder="选择推送平台"
              style="width: 100%;"
              :disabled="isEdit"
            >
              <el-option label="企业微信" value="wecom">
                <div class="platform-option">
                  <span class="platform-icon">💼</span>
                  <span>企业微信</span>
                </div>
              </el-option>
              <el-option label="Git (远程同步)" value="git">
                <div class="platform-option">
                  <span class="platform-icon">📦</span>
                  <span>Git (远程同步)</span>
                </div>
              </el-option>
              <el-option label="Obsidian (本地 API)" value="obsidian_local">
                <div class="platform-option">
                  <span class="platform-icon">📁</span>
                  <span>Obsidian (本地 API)</span>
                </div>
              </el-option>
            </el-select>
          </el-form-item>

          <el-form-item
            v-if="form.platform === 'wecom'"
            label="Webhook Key"
            prop="webhook_key"
          >
            <el-input
              v-model="form.webhook_key"
              type="password"
              show-password
              :placeholder="isEdit ? '留空则保持不变' : '请输入企业微信Webhook Key'"
            />
          </el-form-item>
        </div>

        <!-- 第二步：推送配置（默认展开） -->
        <div class="form-section">
          <div class="section-title">
            <span class="step-badge">2</span>
            推送配置
            <el-tag size="small" type="success">常用</el-tag>
          </div>

          <!-- 高分即时推送 -->
          <div class="push-group">
            <div class="push-group__header">
              <el-switch v-model="form.push_immediate_enabled" />
              <span class="push-group__label">高分即时推送</span>
              <span class="push-group__desc">评分≥阈值时立即推送</span>
            </div>
            <el-form-item v-if="form.push_immediate_enabled" class="push-group__slider">
              <div class="threshold-control">
                <span class="threshold-label">阈值</span>
                <el-slider
                  v-model="form.push_immediate_threshold"
                  :min="0"
                  :max="100"
                  :step="5"
                  show-input
                  :input-size="'small'"
                />
              </div>
            </el-form-item>
          </div>

          <!-- 日报推送 -->
          <div class="push-group">
            <div class="push-group__header">
              <el-switch v-model="form.push_daily_enabled" />
              <span class="push-group__label">日报推送</span>
              <span class="push-group__desc">每日汇总推送</span>
            </div>
            <template v-if="form.push_daily_enabled">
              <el-form-item class="push-group__slider">
                <div class="threshold-control">
                  <span class="threshold-label">阈值</span>
                  <el-slider
                    v-model="form.push_daily_threshold"
                    :min="0"
                    :max="100"
                    :step="5"
                    show-input
                    :input-size="'small'"
                  />
                </div>
              </el-form-item>
              <el-form-item label="日推送上限">
                <el-input-number
                  v-model="form.push_daily_limit"
                  :min="1"
                  :max="2000"
                  size="small"
                />
                <span class="input-hint">条/天</span>
              </el-form-item>
            </template>
          </div>

          <!-- 周报推送 -->
          <div class="push-group">
            <div class="push-group__header">
              <el-switch v-model="form.push_weekly_enabled" />
              <span class="push-group__label">周报推送</span>
              <span class="push-group__desc">每周一汇总推送</span>
            </div>
            <template v-if="form.push_weekly_enabled">
              <el-form-item class="push-group__slider">
                <div class="threshold-control">
                  <span class="threshold-label">阈值</span>
                  <el-slider
                    v-model="form.push_weekly_threshold"
                    :min="0"
                    :max="100"
                    :step="5"
                    show-input
                    :input-size="'small'"
                  />
                </div>
              </el-form-item>
              <el-form-item label="周推送上限">
                <el-input-number
                  v-model="form.push_weekly_limit"
                  :min="1"
                  :max="2000"
                  size="small"
                />
                <span class="input-hint">条/周</span>
              </el-form-item>
            </template>
          </div>
        </div>

        <!-- 第三步：高级配置（默认折叠） -->
        <div class="form-section advanced-section">
          <el-collapse>
            <el-collapse-item name="advanced">
              <template #title>
                <div class="advanced-header">
                  <span class="step-badge">3</span>
                  <span>高级配置</span>
                  <el-tag size="small" type="info">可选</el-tag>
                </div>
              </template>

              <div class="advanced-content">
                <!-- Git 配置 -->
                <template v-if="form.platform === 'git'">
                  <div class="platform-config">
                    <div class="config-title">
                      <span class="platform-icon">📦</span>
                      Git 远程同步配置
                    </div>

                    <el-form-item label="仓库地址" prop="git_repo_url">
                      <el-input
                        v-model="form.git_repo_url"
                        placeholder="https://github.com/user/repo.git"
                      />
                    </el-form-item>

                    <el-form-item label="分支">
                      <el-input v-model="form.git_branch" placeholder="main" />
                    </el-form-item>

                    <el-form-item label="访问令牌">
                      <el-input
                        v-model="form.git_access_token"
                        type="password"
                        show-password
                        placeholder="GitHub Personal Access Token 或 Deploy Token"
                      />
                    </el-form-item>

                    <el-form-item label="凭证类型">
                      <el-radio-group v-model="form.git_credential_type">
                        <el-radio value="deploy_token">Deploy Token</el-radio>
                        <el-radio value="pat">Personal Access Token</el-radio>
                      </el-radio-group>
                    </el-form-item>

                    <el-form-item label="提交者名称">
                      <el-input v-model="form.git_author_name" placeholder="AI News Bot" />
                    </el-form-item>

                    <el-form-item label="提交者邮箱">
                      <el-input v-model="form.git_author_email" placeholder="bot@example.com" />
                    </el-form-item>

                    <div class="folder-config">
                      <div class="folder-config__title">文件存储路径</div>
                      <el-form-item label="日报文件夹">
                        <el-input v-model="form.git_daily_folder" placeholder="AI-News/Daily" />
                      </el-form-item>
                      <el-form-item label="周报文件夹">
                        <el-input v-model="form.git_weekly_folder" placeholder="AI-News/Weekly" />
                      </el-form-item>
                      <el-form-item label="即时推送文件夹">
                        <el-input v-model="form.git_immediate_folder" placeholder="AI-News/Immediate" />
                      </el-form-item>
                    </div>
                  </div>
                </template>

                <!-- Obsidian Local API 配置 -->
                <template v-if="form.platform === 'obsidian_local'">
                  <div class="platform-config">
                    <div class="config-title">
                      <span class="platform-icon">📁</span>
                      Obsidian Local API 配置
                    </div>

                    <el-form-item label="API 地址" prop="obsidian_api_url">
                      <el-input
                        v-model="form.obsidian_api_url"
                        placeholder="http://localhost:27124"
                      />
                    </el-form-item>

                    <el-form-item label="API 密钥">
                      <el-input
                        v-model="form.obsidian_api_key"
                        type="password"
                        show-password
                        placeholder="Obsidian Local REST API 密钥"
                      />
                    </el-form-item>

                    <el-form-item label="Vault 路径">
                      <el-input v-model="form.obsidian_vault_path" placeholder="D:/Obsidian/Vault" />
                    </el-form-item>

                    <el-form-item label="验证 SSL">
                      <el-switch v-model="form.obsidian_verify_ssl" />
                    </el-form-item>

                    <div class="folder-config">
                      <div class="folder-config__title">文件存储路径</div>
                      <el-form-item label="日报文件夹">
                        <el-input v-model="form.obsidian_daily_folder" placeholder="AI-News/Daily" />
                      </el-form-item>
                      <el-form-item label="周报文件夹">
                        <el-input v-model="form.obsidian_weekly_folder" placeholder="AI-News/Weekly" />
                      </el-form-item>
                      <el-form-item label="即时推送文件夹">
                        <el-input v-model="form.obsidian_immediate_folder" placeholder="AI-News/Immediate" />
                      </el-form-item>
                    </div>
                  </div>
                </template>

                <!-- 全局启用（编辑时所有平台都显示） -->
                <template v-if="isEdit">
                  <el-form-item label="全局启用">
                    <el-switch v-model="form.is_active" />
                  </el-form-item>
                </template>
              </div>
            </el-collapse-item>
          </el-collapse>
        </div>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button
          v-if="form.platform === 'git' || form.platform === 'obsidian_local'"
          :loading="testing"
          @click="handleTestConnection"
        >
          测试连接
        </el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">
          保存配置
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
        </template>
      </el-result>
    </el-dialog>

    <!-- 模板编辑弹窗 -->
    <TemplateEditorDialog
      v-if="editingWebhookId !== null"
      v-model:visible="templateDialogVisible"
      :webhook-id="editingWebhookId"
      @saved="handleTemplateSaved"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, defineAsyncComponent, computed } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { request } from '@/api'

// 模板编辑器 Dialog 懒加载 - 仅在点击编辑按钮时加载
const TemplateEditorDialog = defineAsyncComponent(() =>
  import('@/components/template/TemplateEditorDialog.vue')
)

// Webhook 类型已移至 types/api.ts，这里保留本地接口用于列表渲染
interface Webhook {
  id: number
  name: string
  platform: string
  // === 推送类型开关 ===
  push_immediate_enabled: boolean
  push_daily_enabled: boolean
  push_weekly_enabled: boolean
  // === 推送类型独立阈值 ===
  push_immediate_threshold: number
  push_daily_threshold: number
  push_weekly_threshold: number
  // === 新增：推送数量限制 ===
  push_daily_limit: number
  push_weekly_limit: number
  // === 失败处理 ===
  push_fail_count: number
  push_fail_threshold: number
  is_disabled: boolean
  // === 兼容字段 ===
  push_threshold: number
  push_enabled: boolean
  is_active: boolean
  created_at: string
  // === Obsidian Git 配置 ===
  git_repo_url?: string
  git_branch?: string
  git_credential_type?: string
  git_author_name?: string
  git_author_email?: string
  git_daily_folder?: string
  git_weekly_folder?: string
  git_immediate_folder?: string
  // === Obsidian Local 配置 ===
  obsidian_api_url?: string
  obsidian_vault_path?: string
  obsidian_verify_ssl?: boolean
  obsidian_daily_folder?: string
  obsidian_weekly_folder?: string
  obsidian_immediate_folder?: string
  // === 关联模板 ===
  templates?: Array<{ template_type: string }>
}

const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const webhooks = ref<Webhook[]>([])
const dialogVisible = ref(false)
const testDialogVisible = ref(false)
const isEdit = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()

/** 原始数据快照 - 用于追踪字段修改 */
const originalData = reactive<Record<string, any>>({})

/** 表单数据 - 单一数据源，无双向同步问题 */
const form = reactive({
  name: '',
  platform: 'wecom',
  webhook_key: '',
  git_repo_url: '',
  git_branch: 'main',
  git_access_token: '',
  git_credential_type: 'deploy_token',
  git_author_name: 'AI News Bot',
  git_author_email: '',
  git_daily_folder: 'AI-News/Daily',
  git_weekly_folder: 'AI-News/Weekly',
  git_immediate_folder: 'AI-News/Immediate',
  obsidian_api_url: 'http://localhost:27124',
  obsidian_api_key: '',
  obsidian_vault_path: '',
  obsidian_verify_ssl: true,
  obsidian_daily_folder: 'AI-News/Daily',
  obsidian_weekly_folder: 'AI-News/Weekly',
  obsidian_immediate_folder: 'AI-News/Immediate',
  push_immediate_enabled: true,
  push_daily_enabled: true,
  push_weekly_enabled: true,
  push_immediate_threshold: 85,
  push_daily_threshold: 75,
  push_weekly_threshold: 80,
  push_daily_limit: 500,
  push_weekly_limit: 300,
  push_threshold: 85,
  is_active: true,
})

/** 表单验证规则 */
const formRules = computed<FormRules>(() => ({
  name: [{ required: true, message: '请输入配置名称', trigger: 'blur' }],
  platform: [{ required: true, message: '请选择平台', trigger: 'change' }],
  webhook_key: isEdit.value
    ? []
    : [
        {
          required: true,
          message: '请输入 Webhook Key',
          trigger: 'blur',
          validator: (_rule: any, _value: any, callback: any) => {
            if (form.platform === 'wecom' && !form.webhook_key) {
              callback(new Error('请输入 Webhook Key'))
            } else {
              callback()
            }
          },
        },
      ],
  git_repo_url: [
    {
      required: true,
      message: '请输入仓库地址',
      trigger: 'blur',
      validator: (_rule: any, _value: any, callback: any) => {
        if (form.platform === 'git' && !form.git_repo_url) {
          callback(new Error('请输入仓库地址'))
        } else {
          callback()
        }
      },
    },
  ],
  obsidian_api_url: [
    {
      required: true,
      message: '请输入 API 地址',
      trigger: 'blur',
      validator: (_rule: any, _value: any, callback: any) => {
        if (form.platform === 'obsidian_local' && !form.obsidian_api_url) {
          callback(new Error('请输入 API 地址'))
        } else {
          callback()
        }
      },
    },
  ],
}))

const testResult = reactive({
  success: false,
  message: '',
})

// Template editor state
const templateDialogVisible = ref(false)
const editingWebhookId = ref<number | null>(null)

async function fetchWebhooks() {
  loading.value = true
  try {
    const data = await request.get('/webhooks/')
    webhooks.value = data.items || []
  } catch (e) {
    console.error('获取Webhook列表失败', e)
  } finally {
    loading.value = false
  }
}

function resetForm() {
  form.name = ''
  form.platform = 'wecom'
  form.webhook_key = ''
  form.git_repo_url = ''
  form.git_branch = 'main'
  form.git_access_token = ''
  form.git_credential_type = 'deploy_token'
  form.git_author_name = 'AI News Bot'
  form.git_author_email = ''
  form.git_daily_folder = 'AI-News/Daily'
  form.git_weekly_folder = 'AI-News/Weekly'
  form.git_immediate_folder = 'AI-News/Immediate'
  form.obsidian_api_url = 'http://localhost:27124'
  form.obsidian_api_key = ''
  form.obsidian_vault_path = ''
  form.obsidian_verify_ssl = true
  form.obsidian_daily_folder = 'AI-News/Daily'
  form.obsidian_weekly_folder = 'AI-News/Weekly'
  form.obsidian_immediate_folder = 'AI-News/Immediate'
  form.push_immediate_enabled = true
  form.push_daily_enabled = true
  form.push_weekly_enabled = true
  form.push_immediate_threshold = 85
  form.push_daily_threshold = 75
  form.push_weekly_threshold = 80
  form.push_daily_limit = 500
  form.push_weekly_limit = 300
  form.push_threshold = 85
  form.is_active = true
}

function handleAdd() {
  isEdit.value = false
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function handleEdit(row: Webhook) {
  isEdit.value = true
  editingId.value = row.id
  // 填充表单数据
  form.name = row.name
  form.platform = row.platform
  form.webhook_key = ''
  form.git_repo_url = row.git_repo_url || ''
  form.git_branch = row.git_branch || 'main'
  form.git_access_token = ''
  form.git_credential_type = row.git_credential_type || 'deploy_token'
  form.git_author_name = row.git_author_name || 'AI News Bot'
  form.git_author_email = row.git_author_email || ''
  form.git_daily_folder = row.git_daily_folder || 'AI-News/Daily'
  form.git_weekly_folder = row.git_weekly_folder || 'AI-News/Weekly'
  form.git_immediate_folder = row.git_immediate_folder || 'AI-News/Immediate'
  form.obsidian_api_url = row.obsidian_api_url || 'http://localhost:27124'
  form.obsidian_api_key = ''
  form.obsidian_vault_path = row.obsidian_vault_path || ''
  form.obsidian_verify_ssl = row.obsidian_verify_ssl !== false
  form.obsidian_daily_folder = row.obsidian_daily_folder || 'AI-News/Daily'
  form.obsidian_weekly_folder = row.obsidian_weekly_folder || 'AI-News/Weekly'
  form.obsidian_immediate_folder = row.obsidian_immediate_folder || 'AI-News/Immediate'
  form.push_immediate_enabled = row.push_immediate_enabled
  form.push_daily_enabled = row.push_daily_enabled
  form.push_weekly_enabled = row.push_weekly_enabled
  form.push_immediate_threshold = row.push_immediate_threshold
  form.push_daily_threshold = row.push_daily_threshold
  form.push_weekly_threshold = row.push_weekly_threshold
  form.push_daily_limit = row.push_daily_limit || 500
  form.push_weekly_limit = row.push_weekly_limit || 300
  form.push_threshold = row.push_threshold
  form.is_active = row.is_active
  // 保存原始数据快照，用于比较字段是否被修改
  Object.assign(originalData, {
    name: row.name,
    platform: row.platform,
    webhook_key: '',
    git_repo_url: row.git_repo_url || '',
    git_branch: row.git_branch || 'main',
    git_access_token: '',
    git_credential_type: row.git_credential_type || 'deploy_token',
    git_author_name: row.git_author_name || 'AI News Bot',
    git_author_email: row.git_author_email || '',
    git_daily_folder: row.git_daily_folder || 'AI-News/Daily',
    git_weekly_folder: row.git_weekly_folder || 'AI-News/Weekly',
    git_immediate_folder: row.git_immediate_folder || 'AI-News/Immediate',
    obsidian_api_url: row.obsidian_api_url || 'http://localhost:27124',
    obsidian_api_key: '',
    obsidian_vault_path: row.obsidian_vault_path || '',
    obsidian_verify_ssl: row.obsidian_verify_ssl !== false,
    obsidian_daily_folder: row.obsidian_daily_folder || 'AI-News/Daily',
    obsidian_weekly_folder: row.obsidian_weekly_folder || 'AI-News/Weekly',
    obsidian_immediate_folder: row.obsidian_immediate_folder || 'AI-News/Immediate',
    push_immediate_enabled: row.push_immediate_enabled,
    push_daily_enabled: row.push_daily_enabled,
    push_weekly_enabled: row.push_weekly_enabled,
    push_immediate_threshold: row.push_immediate_threshold,
    push_daily_threshold: row.push_daily_threshold,
    push_weekly_threshold: row.push_weekly_threshold,
    push_daily_limit: row.push_daily_limit || 500,
    push_weekly_limit: row.push_weekly_limit || 300,
    push_threshold: row.push_threshold,
    is_active: row.is_active,
  })
  dialogVisible.value = true
}

async function handleTestConnection() {
  testing.value = true
  testDialogVisible.value = true
  testResult.success = false
  testResult.message = '测试中...'

  try {
    let result
    if (form.platform === 'git') {
      // Git 平台需要填写 repo_url 才能测试
      if (!form.git_repo_url) {
        testResult.success = false
        testResult.message = '请先填写 Git 仓库地址'
        testing.value = false
        return
      }
      result = await request.post('/obsidian/test-connection/git', {
        repo_url: form.git_repo_url,
        branch: form.git_branch || 'main',
        access_token: form.git_access_token,
        credential_type: form.git_credential_type || 'deploy_token',
      })
    } else if (form.platform === 'obsidian_local') {
      result = await request.post('/obsidian/test-connection/local', {
        api_url: form.obsidian_api_url,
        api_key: form.obsidian_api_key,
        vault_path: form.obsidian_vault_path,
        verify_ssl: form.obsidian_verify_ssl !== false,
      })
    } else if (form.platform === 'wecom') {
      // 企业微信不需要连接测试
      testResult.success = true
      testResult.message = '企业微信无需测试连接'
      testing.value = false
      return
    } else {
      testResult.success = false
      testResult.message = '不支持的平台类型'
      testing.value = false
      return
    }
    testResult.success = result.success
    testResult.message = result.message || result.detail || '测试成功'
  } catch (e: any) {
    testResult.success = false
    testResult.message = e.response?.data?.message || e.response?.data?.detail || '测试失败'
  } finally {
    testing.value = false
  }
}

async function handleSave() {
  // 验证表单
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }

  saving.value = true
  try {
    const payload: Record<string, unknown> = {}

    // 核心字段：只有实际修改过才传
    if (form.name !== originalData.name) {
      payload.name = form.name
    }
    if (form.is_active !== originalData.is_active) {
      payload.is_active = form.is_active
    }

    // 新增时必须提供 webhook_key
    if (!isEdit.value) {
      payload.webhook_key = form.webhook_key
      payload.platform = form.platform
    } else {
      // 编辑时只有填写了 webhook_key 才更新
      if (form.webhook_key) {
        payload.webhook_key = form.webhook_key
      }
    }

    // 推送类型开关：只传修改过的
    if (form.push_immediate_enabled !== originalData.push_immediate_enabled) {
      payload.push_immediate_enabled = form.push_immediate_enabled
    }
    if (form.push_daily_enabled !== originalData.push_daily_enabled) {
      payload.push_daily_enabled = form.push_daily_enabled
    }
    if (form.push_weekly_enabled !== originalData.push_weekly_enabled) {
      payload.push_weekly_enabled = form.push_weekly_enabled
    }

    // 推送阈值：只传修改过的
    if (form.push_immediate_threshold !== originalData.push_immediate_threshold) {
      payload.push_immediate_threshold = form.push_immediate_threshold
    }
    if (form.push_daily_threshold !== originalData.push_daily_threshold) {
      payload.push_daily_threshold = form.push_daily_threshold
    }
    if (form.push_weekly_threshold !== originalData.push_weekly_threshold) {
      payload.push_weekly_threshold = form.push_weekly_threshold
    }

    // 推送数量限制：只传修改过的
    if (form.push_daily_limit !== originalData.push_daily_limit) {
      payload.push_daily_limit = form.push_daily_limit
    }
    if (form.push_weekly_limit !== originalData.push_weekly_limit) {
      payload.push_weekly_limit = form.push_weekly_limit
    }

    // 兼容字段
    if (form.push_threshold !== originalData.push_threshold) {
      payload.push_threshold = form.push_threshold
    }

    // Git 配置：只传修改过的
    if (form.platform === 'git') {
      if (form.git_repo_url !== originalData.git_repo_url) {
        payload.git_repo_url = form.git_repo_url
      }
      if (form.git_branch !== originalData.git_branch) {
        payload.git_branch = form.git_branch
      }
      if (form.git_access_token !== originalData.git_access_token) {
        payload.git_access_token = form.git_access_token
      }
      if (form.git_credential_type !== originalData.git_credential_type) {
        payload.git_credential_type = form.git_credential_type
      }
      if (form.git_author_name !== originalData.git_author_name) {
        payload.git_author_name = form.git_author_name
      }
      if (form.git_author_email !== originalData.git_author_email) {
        payload.git_author_email = form.git_author_email
      }
      if (form.git_daily_folder !== originalData.git_daily_folder) {
        payload.git_daily_folder = form.git_daily_folder
      }
      if (form.git_weekly_folder !== originalData.git_weekly_folder) {
        payload.git_weekly_folder = form.git_weekly_folder
      }
      if (form.git_immediate_folder !== originalData.git_immediate_folder) {
        payload.git_immediate_folder = form.git_immediate_folder
      }
    }

    // Obsidian Local API 配置：只传修改过的
    if (form.platform === 'obsidian_local') {
      if (form.obsidian_api_url !== originalData.obsidian_api_url) {
        payload.obsidian_api_url = form.obsidian_api_url
      }
      if (form.obsidian_api_key !== originalData.obsidian_api_key) {
        payload.obsidian_api_key = form.obsidian_api_key
      }
      if (form.obsidian_vault_path !== originalData.obsidian_vault_path) {
        payload.obsidian_vault_path = form.obsidian_vault_path
      }
      if (form.obsidian_verify_ssl !== originalData.obsidian_verify_ssl) {
        payload.obsidian_verify_ssl = form.obsidian_verify_ssl
      }
      if (form.obsidian_daily_folder !== originalData.obsidian_daily_folder) {
        payload.obsidian_daily_folder = form.obsidian_daily_folder
      }
      if (form.obsidian_weekly_folder !== originalData.obsidian_weekly_folder) {
        payload.obsidian_weekly_folder = form.obsidian_weekly_folder
      }
      if (form.obsidian_immediate_folder !== originalData.obsidian_immediate_folder) {
        payload.obsidian_immediate_folder = form.obsidian_immediate_folder
      }
    }

    if (isEdit.value && editingId.value) {
      await request.put(`/webhooks/${editingId.value}`, payload)
    } else {
      await request.post('/webhooks/', payload)
    }

    ElMessage.success('配置已保存')
    dialogVisible.value = false
    await fetchWebhooks()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(row: Webhook) {
  try {
    await request.delete(`/webhooks/${row.id}`)
    ElMessage.success('已删除')
    await fetchWebhooks()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

async function handleTest(row: Webhook) {
  try {
    const data = await request.post(`/webhooks/${row.id}/test`)
    testResult.success = data.success
    testResult.message = data.message
    testDialogVisible.value = true
  } catch (e: any) {
    testResult.success = false
    testResult.message = e.response?.data?.detail || '测试请求失败'
    testDialogVisible.value = true
  }
}

function handleTemplateEdit(row: Webhook) {
  editingWebhookId.value = row.id
  templateDialogVisible.value = true
}

function handleTemplateSaved() {
  // Refresh webhook list if needed
  templateDialogVisible.value = false
}

onMounted(() => {
  fetchWebhooks()
})
</script>

<style scoped>
.webhook-config-page {
  padding: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.cell-text {
  text-align: center;
  word-break: break-word;
  white-space: normal;
  line-height: 1.5;
}

.threshold-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.threshold-value {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.form-group-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-secondary);
  margin: 12px 0 8px;
  padding-left: 4px;
  border-left: 3px solid var(--color-primary);
}

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
  max-width: 500px;
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

/* 卡片列表布局 */
.webhook-card-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
  gap: 16px;
}

.webhook-card {
  background: var(--el-fill-color-light);
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  padding: 16px;
  transition: box-shadow 0.3s ease, border-color 0.3s ease;
}

.webhook-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  border-color: var(--el-color-primary-light-5);
}

/* Webhook 信息区域 */
.webhook-info {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.webhook-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.webhook-title {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.webhook-name {
  font-size: 16px;
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.webhook-status {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.webhook-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.stat-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.stat-value {
  font-size: 13px;
  font-weight: 500;
  color: var(--el-text-color-primary);
}

/* 分隔线 */
.webhook-divider {
  margin: 12px 0;
}

/* 模板区域 */
.template-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.template-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.template-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.template-badges {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.template-badge {
  cursor: default;
}

/* 操作按钮 */
.webhook-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--el-border-color-lighter);
}

/* ========== 表单样式（从 WebhookForm.vue 合并） ========== */
.webhook-form {
  padding: 0 8px;
}

/* 步骤标题 */
.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-bottom: 16px;
}

.step-badge {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  background: var(--el-color-primary);
  color: white;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 600;
}

/* 配置区块 */
.form-section {
  margin-bottom: 24px;
  padding: 16px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
  transition: all 0.3s ease;
}

.form-section:hover {
  background: var(--el-fill-color);
}

/* 平台选项 */
.platform-option {
  display: flex;
  align-items: center;
  gap: 8px;
}

.platform-icon {
  font-size: 16px;
}

/* 推送配置组 */
.push-group {
  margin-bottom: 16px;
  padding: 12px;
  background: var(--el-bg-color);
  border-radius: 6px;
}

.push-group:last-child {
  margin-bottom: 0;
}

.push-group__header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.push-group__label {
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.push-group__desc {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-left: auto;
}

.push-group__slider {
  margin-top: 12px;
  margin-bottom: 0;
}

/* 阈值控制 */
.threshold-control {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
}

.threshold-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  width: 40px;
  flex-shrink: 0;
}

/* 输入提示 */
.input-hint {
  margin-left: 8px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

/* 高级配置折叠项 */
.advanced-section {
  background: transparent;
  padding: 0;
  border: 1px solid var(--el-border-color);
}

.advanced-section:hover {
  border-color: var(--el-color-primary-light-5);
}

.advanced-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
}

.advanced-content {
  padding: 16px 8px;
}

/* 平台特定配置 */
.platform-config {
  margin-bottom: 16px;
}

.config-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 500;
  color: var(--el-text-color-primary);
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px dashed var(--el-border-color);
}

/* 文件夹配置 */
.folder-config {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px dashed var(--el-border-color);
}

.folder-config__title {
  font-size: 13px;
  font-weight: 500;
  color: var(--el-text-color-secondary);
  margin-bottom: 12px;
}

/* 折叠面板样式覆盖 */
:deep(.el-collapse) {
  border: none;
}

:deep(.el-collapse-item__header) {
  background: transparent;
  border: none;
  padding: 12px 16px;
  height: auto;
  line-height: 1.5;
}

:deep(.el-collapse-item__wrap) {
  background: transparent;
  border: none;
}

:deep(.el-collapse-item__content) {
  padding: 0;
}

/* 响应式调整 */
@media (max-width: 500px) {
  .webhook-card-list {
    grid-template-columns: 1fr;
  }

  .webhook-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .webhook-stats {
    flex-direction: column;
    gap: 8px;
  }
}
</style>