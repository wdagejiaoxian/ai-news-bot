<template>
  <div class="config-pipe-input">
    <div class="config-field-row">
      <div class="config-label">
        <span class="config-name">{{ label }}</span>
        <el-tag v-if="config.is_customized" size="small" type="success" effect="plain">
          已自定义
        </el-tag>
      </div>
      <div class="config-controls">
        <div class="pipe-tags">
          <el-tag
            v-for="(tag, idx) in tags"
            :key="idx"
            closable
            size="small"
            :disable-transitions="false"
            @close="removeTag(idx)"
          >
            {{ tag }}
          </el-tag>
          <el-input
            v-if="inputVisible"
            ref="inputRef"
            v-model="inputValue"
            size="small"
            style="width: 120px"
            @keyup.enter="addTag"
            @blur="addTag"
          />
          <el-button v-else size="small" text @click="showInput">+ 添加</el-button>
        </div>
        <el-button
          v-if="config.is_customized"
          text size="small" type="warning"
          :loading="updatingKey === config.key"
          @click="handleReset"
        >恢复默认</el-button>
        <span class="config-default">默认: {{ defaultText }}</span>
      </div>
    </div>
    <div v-if="config.updated_at" class="config-meta">修改于 {{ formatTime(config.updated_at) }}</div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { storeToRefs } from 'pinia'
import { useSystemConfigStore } from '@/store/system-config'
import type { SystemConfigItem } from '@/types/system-config'

const props = defineProps<{
  config: SystemConfigItem
  label: string
}>()

const store = useSystemConfigStore()
const { updatingKey } = storeToRefs(store)

const tags = ref<string[]>([])
const inputVisible = ref(false)
const inputValue = ref('')
const inputRef = ref<HTMLInputElement>()

function parseTags(val: string | number | boolean): string[] {
  return String(val).split('|').map(s => s.trim()).filter(Boolean)
}

watch(() => props.config.current_value, (nv) => {
  tags.value = parseTags(nv)
}, { immediate: true })

const defaultText = computed(() => {
  const parts = parseTags(props.config.default_value)
  return parts.length > 3 ? parts.slice(0, 3).join(', ') + '...' : parts.join(', ') || '(空)'
})

function showInput() {
  inputVisible.value = true
  nextTick(() => inputRef.value?.focus())
}

function addTag() {
  const val = inputValue.value.trim()
  if (val && !tags.value.includes(val)) {
    tags.value.push(val)
    saveTags()
  }
  inputVisible.value = false
  inputValue.value = ''
}

function removeTag(idx: number) {
  tags.value.splice(idx, 1)
  saveTags()
}

async function saveTags() {
  const joined = tags.value.join('|')
  if (joined === String(props.config.default_value)) {
    await store.resetByKey(props.config.key)
  } else {
    await store.updateByKey(props.config.key, joined)
  }
}

async function handleReset() { await store.resetByKey(props.config.key) }

function formatTime(t: string) {
  try { return new Date(t).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) }
  catch { return t }
}
</script>

<style scoped>
.config-pipe-input { padding: 12px 0; border-bottom: 1px solid var(--el-border-color-light); }
.config-pipe-input:last-child { border-bottom: none; }
.config-field-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.config-label { display: flex; align-items: center; gap: 8px; min-width: 140px; }
.config-name { font-size: 14px; font-weight: 500; color: var(--el-text-color-primary); white-space: nowrap; }
.config-controls { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; flex: 1; justify-content: flex-end; }
.pipe-tags { display: flex; align-items: center; gap: 4px; flex-wrap: wrap; max-width: 400px; }
.config-default { font-size: 12px; color: var(--el-text-color-secondary); }
.config-meta { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 4px; padding-left: 148px; }
</style>
