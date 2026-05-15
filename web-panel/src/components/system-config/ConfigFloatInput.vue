<template>
  <div class="config-float-input">
    <div class="config-field-row">
      <div class="config-label">
        <span class="config-name">{{ label }}</span>
        <el-tag v-if="config.is_customized" size="small" type="success" effect="plain" class="customized-tag">
          已自定义
        </el-tag>
      </div>
      <div class="config-controls">
        <el-input-number
          v-model="localValue"
          :precision="2"
          :step="0.01"
          :min="0"
          :disabled="updatingKey === config.key"
          :controls-position="'right'"
          size="small"
          style="width: 180px"
          @change="handleChange"
        />
        <el-button
          v-if="config.is_customized"
          text size="small" type="warning"
          :loading="updatingKey === config.key"
          @click="handleReset"
        >恢复默认</el-button>
        <span class="config-default">默认: {{ config.default_value }}</span>
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

const localValue = ref<number>(props.config.current_value as number)

watch(() => props.config.current_value, (nv) => { localValue.value = nv as number })

async function handleChange(val: number | undefined) {
  if (val === undefined) return
  if (val === props.config.default_value) {
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
.config-float-input { padding: 12px 0; border-bottom: 1px solid var(--el-border-color-light); }
.config-float-input:last-child { border-bottom: none; }
.config-field-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.config-label { display: flex; align-items: center; gap: 8px; min-width: 140px; }
.config-name { font-size: 14px; font-weight: 500; color: var(--el-text-color-primary); white-space: nowrap; }
.customized-tag { flex-shrink: 0; }
.config-controls { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.config-default { font-size: 12px; color: var(--el-text-color-secondary); }
.config-meta { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 4px; padding-left: 148px; }
</style>
