<template>
  <div class="variable-panel">
    <el-collapse v-model="activeNames" accordion>
      <!-- 上下文变量 -->
      <el-collapse-item title="上下文变量" name="context">
        <template #title>
          <div class="collapse-title">
            <el-icon><Calendar /></el-icon>
            <span>上下文变量</span>
          </div>
        </template>
        <div class="variable-list">
          <el-tooltip
            v-for="v in contextVariables"
            :key="v.key"
            :content="v.description"
            placement="top"
          >
            <el-tag
              class="variable-tag context-tag"
              @click="handleInsert(v.key)"
            >
              {{ v.key }}
            </el-tag>
          </el-tooltip>
        </div>
      </el-collapse-item>

      <!-- GitHub 循环变量 -->
      <el-collapse-item title="GitHub 变量" name="github">
        <template #title>
          <div class="collapse-title">
            <el-icon><Connection /></el-icon>
            <span>GitHub 变量</span>
          </div>
        </template>
        <div class="variable-list">
          <el-tooltip
            v-for="v in githubVariables"
            :key="v.key"
            :content="v.description"
            placement="top"
          >
            <el-tag
              class="variable-tag github-tag"
              @click="handleInsert(v.key)"
            >
              {{ v.key }}
            </el-tag>
          </el-tooltip>
        </div>
        <div class="loop-hint">
          <el-icon><InfoFilled /></el-icon>
          <span>在 &#123;&#123;#github_loop&#125;&#125; 块内使用</span>
        </div>
      </el-collapse-item>

      <!-- 文章循环变量 -->
      <el-collapse-item title="文章变量" name="article">
        <template #title>
          <div class="collapse-title">
            <el-icon><Document /></el-icon>
            <span>文章变量</span>
          </div>
        </template>
        <div class="variable-list">
          <el-tooltip
            v-for="v in articleVariables"
            :key="v.key"
            :content="v.description"
            placement="top"
          >
            <el-tag
              class="variable-tag article-tag"
              @click="handleInsert(v.key)"
            >
              {{ v.key }}
            </el-tag>
          </el-tooltip>
        </div>
        <div class="loop-hint">
          <el-icon><InfoFilled /></el-icon>
          <span>在 &#123;&#123;#article_loop&#125;&#125; 块内使用</span>
        </div>
      </el-collapse-item>

      <!-- 循环块 -->
      <el-collapse-item title="循环块" name="loops">
        <template #title>
          <div class="collapse-title">
            <el-icon><Refresh /></el-icon>
            <span>循环块</span>
          </div>
        </template>
        <div class="loop-buttons">
          <el-button @click="handleInsertLoop('github_loop')">
            <el-icon><Connection /></el-icon>
            GitHub 循环
          </el-button>
          <el-button @click="handleInsertLoop('article_loop')">
            <el-icon><Document /></el-icon>
            文章循环
          </el-button>
        </div>
        <div class="loop-syntax">
          <code>&#123;&#123;#github_loop&#125;&#125;...&#123;&#123;/github_loop&#125;&#125;</code>
          <code>&#123;&#123;#article_loop&#125;&#125;...&#123;&#123;/article_loop&#125;&#125;</code>
        </div>
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{
  modelValue: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  'insert-variable': [variable: string]
  'insert-loop': [loopType: string]
}>()

const activeNames = ref(['context'])

// 上下文变量
const contextVariables = [
  { key: '{{date}}', description: '当前日期，格式：YYYY-MM-DD' },
  { key: '{{week_start}}', description: '本周开始日期' },
  { key: '{{week_end}}', description: '本周结束日期' },
  { key: '{{generated_at}}', description: '报告生成时间' },
  { key: '{{week_number}}', description: '年内周序号' },
  { key: '{{github_count}}', description: 'GitHub 项目总数' },
  { key: '{{app_name}}', description: '应用名称：AI News Bot' },
]

// GitHub 变量
const githubVariables = [
  { key: '{{github.full_name}}', description: '项目全名 (owner/repo)' },
  { key: '{{github.url}}', description: '项目 URL 地址' },
  { key: '{{github.stars}}', description: '星标数量' },
  { key: '{{github.stars_today}}', description: '今日新增星标' },
  { key: '{{github.language}}', description: '主要编程语言' },
  { key: '{{github.description}}', description: '项目描述' },
  { key: '{{github.index}}', description: '序号 (从 1 开始)' },
]

// 文章变量
const articleVariables = [
  { key: '{{article.title}}', description: '文章标题' },
  { key: '{{article.url}}', description: '文章 URL 地址' },
  { key: '{{article.score}}', description: 'AI 评分 (0-100)' },
  { key: '{{article.summary}}', description: 'AI 生成的摘要' },
  { key: '{{article.tags}}', description: '文章标签 (逗号分隔)' },
  { key: '{{article.source_name}}', description: '文章来源名称' },
  { key: '{{article.index}}', description: '序号 (从 1 开始)' },
]

function handleInsert(variable: string) {
  emit('insert-variable', variable)
}

function handleInsertLoop(loopType: string) {
  const loopBlock = `{{#${loopType}}}...{{/${loopType}}}`
  emit('insert-loop', loopBlock)
}
</script>

<style scoped>
.variable-panel {
  height: 100%;
  overflow-y: auto;
}

.collapse-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
}

.variable-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px 0;
}

.variable-tag {
  cursor: pointer;
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', monospace;
  font-size: 12px;
  transition: all 0.2s ease;
}

.variable-tag:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.context-tag {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  border: none;
}

.github-tag {
  background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
  color: #fff;
  border: none;
}

.article-tag {
  background: linear-gradient(135deg, #fc4a1a 0%, #f7b733 100%);
  color: #fff;
  border: none;
}

.loop-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 12px;
  padding: 8px 12px;
  background: var(--el-fill-color-light);
  border-radius: 6px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.loop-buttons {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.loop-syntax {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.loop-syntax code {
  background: var(--el-fill-color);
  padding: 6px 10px;
  border-radius: 4px;
  font-size: 11px;
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', monospace;
  color: var(--el-text-color-secondary);
}

:deep(.el-collapse-item__header) {
  font-weight: 500;
}

:deep(.el-collapse-item__content) {
  padding-bottom: 16px;
}
</style>