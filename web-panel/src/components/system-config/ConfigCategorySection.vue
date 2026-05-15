<template>
  <div class="config-category-section">
    <div class="category-header">
      <span class="category-title">{{ title }}</span>
      <span class="category-count">{{ customizedCount }}/{{ configs.length }} 已自定义</span>
    </div>
    <div class="category-body">
      <template v-for="config in configs" :key="config.key">
        <ConfigIntInput
          v-if="config.value_type === 'int' && !isPipeConfig(config.key)"
          :config="config"
          :label="getLabel(config.key)"
        />
        <ConfigFloatInput
          v-else-if="config.value_type === 'float'"
          :config="config"
          :label="getLabel(config.key)"
        />
        <ConfigBoolSwitch
          v-else-if="config.value_type === 'bool'"
          :config="config"
          :label="getLabel(config.key)"
        />
        <ConfigPipeStringInput
          v-else-if="isPipeConfig(config.key)"
          :config="config"
          :label="getLabel(config.key)"
        />
        <ConfigStringInput
          v-else
          :config="config"
          :label="getLabel(config.key)"
        />
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { SystemConfigItem } from '@/types/system-config'
import ConfigIntInput from './ConfigIntInput.vue'
import ConfigFloatInput from './ConfigFloatInput.vue'
import ConfigStringInput from './ConfigStringInput.vue'
import ConfigBoolSwitch from './ConfigBoolSwitch.vue'
import ConfigPipeStringInput from './ConfigPipeStringInput.vue'

const props = defineProps<{
  title: string
  configs: SystemConfigItem[]
}>()

const customizedCount = computed(() =>
  props.configs.filter(c => c.is_customized).length,
)

const PIPE_KEYS = new Set(['trafilatura_skip_domains', 'default_github_languages'])

function isPipeConfig(key: string): boolean {
  return PIPE_KEYS.has(key)
}

const LABEL_MAP: Record<string, string> = {
  push_score_threshold: '内容价值保留基线',
  rss_concurrent_limit: 'RSS 并发采集数',
  rss_error_threshold: 'RSS 错误禁用阈值',
  rss_fetch_timeout: 'RSS 采集超时（秒）',
  process_batch_size: '每批处理文章数',
  process_max_total: '每次最多处理数',
  process_batch_delay: '批次间延迟（秒）',
  article_save_batch_size: '批量保存每批数量',
  trafilatura_skip_domains: '跳过内容补全域名',
  trafilatura_enable_immediate_enrichment: '采集时同步补全内容',
  enrich_concurrency: '内容补全并发数',
  enrich_timeout: '单篇补全超时（秒）',
  enrich_min_content_length: '补全最小字符数',
  dynamic_skip_enabled: '启用动态域名跳过',
  dynamic_skip_threshold: '域名跳过连续失败次数',
  github_token: 'GitHub API Token',
  default_github_languages: '默认监控语言',
  github_api_base_url: 'GitHub API 地址',
  rsshub_enabled: '启用 RSSHub',
  rsshub_url: 'RSSHub 服务地址',
  semantic_cache_max_sessions: '语义缓存最大会话数',
  semantic_cache_ttl_seconds: '语义缓存 TTL（秒）',
  semantic_search_max_results: '语义搜索最大返回数',
  embedding_max_text_length: 'Embedding 最大文本长度',
  ollama_embedding_base_url: 'Embedding 服务地址',
  dedup_similarity_threshold: '语义去重相似度阈值',
  cache_similarity_threshold: '缓存命中相似度阈值',
  embedding_timeout: 'Embedding 生成超时（秒）',
  llm_api_timeout: 'LLM API 测试超时（秒）',
  batch_llm_timeout: '批次 LLM 处理超时（秒）',
  llm_max_retries: 'LLM 最大重试次数',
  embedding_max_retries: 'Embedding 最大重试次数',
  webhook_api_timeout: 'Webhook API 超时（秒）',
  wecom_webhook_timeout: '企业微信 Webhook 超时（秒）',
  wecom_api_timeout: '企业微信 API 超时（秒）',
  wecom_upload_timeout: '企业微信上传超时（秒）',
  wecom_api_base_url: '企业微信 API 地址',
  cleanup_days_threshold_min: '低分文章清理天数',
  cleanup_days_threshold_max: '过期文章清理天数',
  push_log_retention_days: '推送日志保留天数',
  task_history_retention_days: '任务历史保留天数',
  operation_log_retention_days: '操作日志保留天数',
  indexer_concurrency: '向量索引器并发数',
  command_default_limit: '命令默认返回数',
  command_preview_limit: '命令预览返回数',
  semantic_search_top_k: '语义搜索返回上限',
  semantic_cache_top_k: '语义缓存查找数量',
  ollama_base_url: 'Ollama 地址',
  ollama_model: 'Ollama 模型',
}

function getLabel(key: string): string {
  return LABEL_MAP[key] || key
}
</script>

<style scoped>
.config-category-section {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  overflow: hidden;
}
.category-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--el-fill-color-light);
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.category-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.category-count {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.category-body {
  padding: 0 16px;
}
</style>
