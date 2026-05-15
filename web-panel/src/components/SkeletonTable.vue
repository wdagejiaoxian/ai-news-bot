<template>
  <div class="skeleton-table">
    <el-table>
      <el-table-column
        v-for="col in columns"
        :key="col.prop"
        :prop="col.prop"
        :label="col.label"
        :width="col.width"
      >
        <template #default>
          <el-skeleton :loading="loading" animated :throttle="100">
            <template #template>
              <el-skeleton-item variant="text" class="skeleton-cell" />
            </template>
          </el-skeleton>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
interface Column {
  prop: string
  label: string
  width?: string
}

interface Props {
  loading?: boolean
  columns?: Column[]
  rows?: number
}

withDefaults(defineProps<Props>(), {
  loading: true,
  columns: () => [
    { prop: 'col1', label: '列1', width: '120' },
    { prop: 'col2', label: '列2' },
    { prop: 'col3', label: '列3', width: '100' },
  ],
  rows: 5,
})
</script>

<style scoped>
.skeleton-table {
  width: 100%;
}

.skeleton-cell {
  width: 80%;
  height: 16px;
}

:deep(.el-table) {
  background: transparent;
}

:deep(.el-table__header th) {
  background: var(--color-bg-content);
}
</style>
