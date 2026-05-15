<template>
  <div class="system-settings-page">
    <!-- 页面头 -->
    <el-card shadow="never" class="header-card">
      <div class="page-header">
        <div class="header-left">
          <h2 class="page-title">系统参数配置</h2>
          <p class="page-desc">修改后即时生效，无需重启应用。敏感配置自动加密存储。</p>
        </div>
        <div class="header-right">
          <el-statistic title="已自定义" :value="store.customizedCount" />
          <el-statistic title="可配置总数" :value="store.totalCount" />
        </div>
      </div>
    </el-card>

    <!-- 分类配置区 -->
    <div v-loading="store.loading" class="categories-container">
      <template v-for="cat in store.categories" :key="cat">
        <ConfigCategorySection
          :title="getCategoryTitle(cat)"
          :configs="store.configsByCategory[cat]"
          class="category-section-gap"
        />
      </template>

      <!-- 空状态 -->
      <el-empty v-if="!store.loading && store.configs.length === 0" description="暂无配置数据" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useSystemConfigStore, CATEGORY_LABELS } from '@/store/system-config'
import ConfigCategorySection from '@/components/system-config/ConfigCategorySection.vue'

const store = useSystemConfigStore()

const CATEGORY_TITLES: Record<string, string> = {
  score: '📊 评分推送',
  rss: '📡 RSS 采集',
  process: '🔧 内容处理',
  enrich: '📝 内容补全',
  domain_skip: '🚫 域名管理',
  github: '🔐 GitHub 设置',
  rsshub: '🌐 RSSHub',
  vector: '🔍 向量搜索',
  timeout: '⏱ 超时重试',
  wecom: '💬 企业微信',
  scheduler_cleanup: '🧹 调度清理',
}

function getCategoryTitle(cat: string): string {
  return CATEGORY_TITLES[cat] || CATEGORY_LABELS[cat] || cat
}

onMounted(() => {
  store.fetchAll()
})
</script>

<style scoped>
.system-settings-page {
  max-width: 960px;
  margin: 0 auto;
}

.header-card {
  margin-bottom: 20px;
  border-radius: 8px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-left {
  flex: 1;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin: 0 0 4px 0;
}

.page-desc {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin: 0;
}

.header-right {
  display: flex;
  gap: 32px;
}

.categories-container {
  min-height: 200px;
}

.category-section-gap {
  margin-bottom: 16px;
}
</style>
