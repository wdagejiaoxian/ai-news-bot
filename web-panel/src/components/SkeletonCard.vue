<template>
  <div class="skeleton-card" :style="{ width, height }">
    <el-skeleton :loading="loading" animated :throttle="100">
      <template #template>
        <!-- 标题骨架 -->
        <el-skeleton-item variant="text" class="skeleton-title" />
        <!-- 内容行 -->
        <el-skeleton-item
          v-for="i in rows"
          :key="i"
          variant="text"
          class="skeleton-row"
          :style="{ width: getRowWidth(i) }"
        />
        <!-- 可选底部 -->
        <slot name="footer" />
      </template>
      <template #default>
        <slot />
      </template>
    </el-skeleton>
  </div>
</template>

<script setup lang="ts">
interface Props {
  loading?: boolean
  rows?: number
  width?: string
  height?: string
}

withDefaults(defineProps<Props>(), {
  loading: true,
  rows: 3,
  width: '100%',
  height: 'auto',
})

function getRowWidth(index: number): string {
  // 最后一行稍短
  if (index === 3) return '60%'
  if (index === 2) return '85%'
  return '100%'
}
</script>

<style scoped>
.skeleton-card {
  padding: var(--spacing-md);
  background: var(--color-bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border);
}

.skeleton-title {
  width: 40%;
  height: 24px;
  margin-bottom: var(--spacing-md);
}

.skeleton-row {
  height: 16px;
  margin-bottom: var(--spacing-sm);
}
</style>
