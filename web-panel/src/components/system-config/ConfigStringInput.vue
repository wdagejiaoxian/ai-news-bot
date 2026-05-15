<template>
  <div class="config-string-input">
    <div class="config-field-row">
      <div class="config-label">
        <span class="config-name">{{ label }}</span>
        <el-tag v-if="config.is_customized" size="small" type="success" effect="plain" class="customized-tag">
          已自定义
        </el-tag>
      </div>
      <div class="config-controls">
        <el-input
          v-model="localValue"
          :type="config.is_encrypted ? 'password' : 'text'"
          :show-password="config.is_encrypted"
          :disabled="updatingKey === config.key"
          size="small"
          style="width: 320px"
          :placeholder="config.is_encrypted ? '已加密，留空则不修改' : '请输入...'"
          clearable
          @change="handleChange"
        />
        <el-button
          v-if="config.is_customized"
          text size="small" type="warning"
          :loading="updatingKey === config.key"
          @click="handleReset"
        >恢复默认</el-button>
        <span class="config-default">默认: {{ config.default_value || '(空)' }}</span>
      </div>
    </div>
    <div v-if="config.updated_at" class="config-meta">修改于 {{ formatTime(config.updated_at) }}</div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useSystemConfigStore } from '@/store/system-config'
import type { SystemConfigItem } from '@/types/system-config'

const props = defineProps<{
  config: SystemConfigItem
  label: string
}>()

const store = useSystemConfigStore()
const { updatingKey } = storeToRefs(store)

const localValue = ref<string>(
  props.config.is_encrypted ? '' : (props.config.current_value as string),
)

watch(() => props.config.current_value, (nv) => {
  if (!props.config.is_encrypted) {
    localValue.value = nv as string
  }
})

async function handleChange(val: string | undefined) {
  if (val === undefined || val === '') return
  if (val === String(props.config.default_value)) {
    await store.resetByKey(props.config.key)
  } else {
    await store.updateByKey(props.config.key, val)
  }
}

async function handleReset() { await store.resetByKey(props.config.key) }

function formatTime(t: string) {
  try { return new Date(t).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) }
  catch { return t }
}
</script>

<style scoped>
.config-string-input { padding: 12px 0; border-bottom: 1px solid var(--el-border-color-light); }
.config-string-input:last-child { border-bottom: none; }
.config-field-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.config-label { display: flex; align-items: center; gap: 8px; min-width: 140px; }
.config-name { font-size: 14px; font-weight: 500; color: var(--el-text-color-primary); white-space: nowrap; }
.customized-tag { flex-shrink: 0; }
.config-controls { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; flex: 1; justify-content: flex-end; }
.config-default { font-size: 12px; color: var(--el-text-color-secondary); }
.config-meta { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 4px; padding-left: 148px; }
</style>
