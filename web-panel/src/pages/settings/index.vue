<template>
  <div class="settings-page">
    <el-card shadow="never" class="settings-card" v-loading="loading">
      <template #header>
        <span class="card-title">系统设置</span>
      </template>

      <el-descriptions :column="2" border>
        <el-descriptions-item label="用户名">{{ userInfo?.username }}</el-descriptions-item>
        <el-descriptions-item label="角色">
          <el-tag :type="userInfo?.role === 'admin' ? 'danger' : 'primary'">
            {{ userInfo?.role === 'admin' ? '管理员' : '业务用户' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="注册时间">
          {{ userInfo?.created_at ? formatDate(userInfo.created_at) : '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="userInfo?.is_active ? 'success' : 'danger'">
            {{ userInfo?.is_active ? '正常' : '已禁用' }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>

      <el-divider />

      <h3 class="section-title">快捷配置</h3>
      <el-row :gutter="16">
        <el-col :xs="24" :sm="12" :md="6">
          <el-card shadow="hover" class="config-card" @click="$router.push('/user-llm-config')">
            <div class="config-icon config-icon--blue">
              <el-icon :size="28"><Cpu /></el-icon>
            </div>
            <h4 class="config-title">我的LLM</h4>
            <p class="config-desc">配置AI模型</p>
          </el-card>
        </el-col>
        <el-col :xs="24" :sm="12" :md="6">
          <el-card shadow="hover" class="config-card" @click="$router.push('/user-llm-config')">
            <div class="config-icon config-icon--purple">
              <el-icon :size="28"><Setting /></el-icon>
            </div>
            <h4 class="config-title">LLM全局</h4>
            <p class="config-desc">全局LLM设置</p>
          </el-card>
        </el-col>
        <el-col :xs="24" :sm="12" :md="6">
          <el-card shadow="hover" class="config-card" @click="$router.push('/webhook-config')">
            <div class="config-icon config-icon--green">
              <el-icon :size="28"><Bell /></el-icon>
            </div>
            <h4 class="config-title">Webhook</h4>
            <p class="config-desc">配置推送地址</p>
          </el-card>
        </el-col>
        <el-col :xs="24" :sm="12" :md="6">
          <el-card shadow="hover" class="config-card" @click="$router.push('/rss')">
            <div class="config-icon config-icon--orange">
              <el-icon :size="28"><Connection /></el-icon>
            </div>
            <h4 class="config-title">RSS源</h4>
            <p class="config-desc">管理订阅源</p>
          </el-card>
        </el-col>
        <el-col :xs="24" :sm="12" :md="6">
          <el-card shadow="hover" class="config-card" @click="$router.push('/system-settings')">
            <div class="config-icon config-icon--cyan">
              <el-icon :size="28"><Tools /></el-icon>
            </div>
            <h4 class="config-title">系统参数</h4>
            <p class="config-desc">动态配置运行时参数</p>
          </el-card>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/store'
import dayjs from 'dayjs'
import { Cpu, Setting, Bell, Connection, Tools } from '@element-plus/icons-vue'

const userStore = useUserStore()
const { userInfo } = storeToRefs(userStore)
const loading = ref(false)

function formatDate(date: string) {
  return date ? dayjs(date).format('YYYY-MM-DD HH:mm') : '-'
}

onMounted(async () => {
  if (!userInfo.value) {
    loading.value = true
    try {
      await userStore.fetchUserInfo()
    } catch (e) {
      ElMessage.error('获取用户信息失败')
    } finally {
      loading.value = false
    }
  }
})
</script>

<style scoped>
.settings-page {
  padding: 0;
}

.settings-card {
  border-radius: var(--radius-2xl);
}

.card-title {
  font-family: var(--font-family-display);
  font-size: var(--font-size-h4);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}

.section-title {
  font-size: var(--font-size-body);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  margin: 0 0 var(--spacing-md) 0;
}

.config-card {
  text-align: center;
  padding: var(--spacing-lg);
  cursor: pointer;
  border-radius: var(--radius-xl);
  transition:
    transform var(--transition-duration-fast) var(--transition-timing),
    box-shadow var(--transition-duration-fast) var(--transition-timing);
  margin-bottom: var(--spacing-md);
}

.config-card:hover {
  transform: translateY(-6px);
  box-shadow: var(--shadow-brand);
}

.config-icon {
  width: 56px;
  height: 56px;
  border-radius: var(--radius-2xl);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto var(--spacing-md) auto;
  color: var(--color-text-inverse);
  transition: transform var(--transition-duration-fast) var(--transition-timing);
}

.config-card:hover .config-icon {
  transform: scale(1.1) rotate(-5deg);
}

.config-icon--blue {
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-light) 100%);
}

.config-icon--purple {
  background: linear-gradient(135deg, var(--color-purple) 0%, var(--color-purple-light) 100%);
}

.config-icon--green {
  background: linear-gradient(135deg, var(--color-success) 0%, var(--color-green-light) 100%);
}

.config-icon--orange {
  background: linear-gradient(135deg, var(--color-warning) 0%, var(--color-orange-light) 100%);
}

.config-icon--cyan {
  background: linear-gradient(135deg, var(--color-info) 0%, var(--color-blue-light) 100%);
}

.config-title {
  font-size: var(--font-size-body);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  margin: 0 0 var(--spacing-xs) 0;
}

.config-desc {
  font-size: var(--font-size-small);
  color: var(--color-text-secondary);
  margin: 0;
}

@media (max-width: 767px) {
  .config-card {
    padding: var(--spacing-md);
  }
}
</style>
