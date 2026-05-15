<template>
  <div class="loop-block-controls">
    <el-dropdown @command="handleInsertLoop" trigger="click">
      <el-button type="primary" plain>
        <el-icon><Plus /></el-icon>
        插入循环块
        <el-icon class="el-icon--right"><ArrowDown /></el-icon>
      </el-button>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item command="github_loop">
            <div class="loop-option">
              <el-icon class="loop-icon github"><Connection /></el-icon>
              <div class="loop-info">
                <span class="loop-name">GitHub 循环</span>
                <span class="loop-syntax">&#123;&#123;#github_loop&#125;&#125;...&#123;&#123;/github_loop&#125;&#125;</span>
              </div>
            </div>
          </el-dropdown-item>
          <el-dropdown-item command="article_loop">
            <div class="loop-option">
              <el-icon class="loop-icon article"><Document /></el-icon>
              <div class="loop-info">
                <span class="loop-name">文章循环</span>
                <span class="loop-syntax">&#123;&#123;#article_loop&#125;&#125;...&#123;&#123;/article_loop&#125;&#125;</span>
              </div>
            </div>
          </el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>

    <!-- Loop block visual indicators -->
    <div v-if="existingLoops.length > 0" class="existing-loops">
      <div class="loops-title">模板中的循环块：</div>
      <div class="loop-tags">
        <el-tag
          v-for="(loop, index) in existingLoops"
          :key="index"
          :type="loop.type === 'github_loop' ? 'success' : 'warning'"
          closable
          @close="handleRemoveLoop(loop)"
          class="loop-tag"
        >
          <el-icon class="loop-tag-icon">
            <Connection v-if="loop.type === 'github_loop'" />
            <Document v-else />
          </el-icon>
          {{ loop.type === 'github_loop' ? 'GitHub' : '文章' }} 循环
        </el-tag>
      </div>
    </div>

    <!-- Loop block syntax reference -->
    <div class="loop-reference">
      <div class="reference-title">
        <el-icon><InfoFilled /></el-icon>
        循环块语法说明
      </div>
      <div class="reference-content">
        <div class="reference-item">
          <span class="ref-label">GitHub 循环：</span>
          <code>&#123;&#123;#github_loop&#125;&#125;...&#123;&#123;/github_loop&#125;&#125;</code>
        </div>
        <div class="reference-item">
          <span class="ref-label">文章循环：</span>
          <code>&#123;&#123;#article_loop&#125;&#125;...&#123;&#123;/article_loop&#125;&#125;</code>
        </div>
      </div>
      <div class="reference-note">
        循环块内的变量会在每次迭代时被替换为对应的数据
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Connection, Document, InfoFilled } from '@element-plus/icons-vue'

interface LoopInfo {
  type: 'github_loop' | 'article_loop'
  startIndex: number
  endIndex: number
}

const props = defineProps<{
  modelValue: string
}>()

const emit = defineEmits<{
  'insert': [loopType: string]
  'remove': [loopBlock: string]
}>()

// Parse existing loops in template
const existingLoops = computed<LoopInfo[]>(() => {
  const content = props.modelValue
  const loops: LoopInfo[] = []

  const githubMatch = content.match(/\{\{#github_loop\}\}/g)
  if (githubMatch) {
    const startPositions = [...content.matchAll(/\{\{#github_loop\}\}/g)].map(m => m.index!)
    startPositions.forEach(start => {
      loops.push({
        type: 'github_loop',
        startIndex: start,
        endIndex: start + '{{#github_loop}}'.length
      })
    })
  }

  const articleMatch = content.match(/\{\{#article_loop\}\}/g)
  if (articleMatch) {
    const startPositions = [...content.matchAll(/\{\{#article_loop\}\}/g)].map(m => m.index!)
    startPositions.forEach(start => {
      loops.push({
        type: 'article_loop',
        startIndex: start,
        endIndex: start + '{{#article_loop}}'.length
      })
    })
  }

  return loops.sort((a, b) => a.startIndex - b.startIndex)
})

function handleInsertLoop(loopType: string) {
  emit('insert', loopType)
}

function handleRemoveLoop(loop: LoopInfo) {
  const fullBlock = loop.type === 'github_loop'
    ? '{{#github_loop}}...{{/github_loop}}'
    : '{{#article_loop}}...{{/article_loop}}'
  emit('remove', fullBlock)
}
</script>

<style scoped>
.loop-block-controls {
  padding: 16px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
}

.existing-loops {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--el-border-color);
}

.loops-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px;
}

.loop-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.loop-tag {
  display: flex;
  align-items: center;
  gap: 4px;
}

.loop-tag-icon {
  font-size: 14px;
}

.loop-reference {
  margin-top: 16px;
  padding: 12px;
  background: var(--el-bg-color);
  border-radius: 6px;
  border: 1px solid var(--el-border-color);
}

.reference-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 500;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px;
}

.reference-content {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.reference-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.ref-label {
  color: var(--el-text-color-secondary);
  min-width: 80px;
}

.reference-item code {
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', monospace;
  font-size: 11px;
  background: var(--el-fill-color);
  padding: 4px 8px;
  border-radius: 4px;
  color: var(--el-color-primary);
}

.reference-note {
  margin-top: 8px;
  font-size: 11px;
  color: var(--el-text-color-placeholder);
}

.loop-option {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 4px 0;
}

.loop-icon {
  font-size: 18px;
}

.loop-icon.github {
  color: #11998e;
}

.loop-icon.article {
  color: #f7b733;
}

.loop-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.loop-name {
  font-weight: 500;
}

.loop-syntax {
  font-size: 11px;
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', monospace;
  color: var(--el-text-color-secondary);
}
</style>