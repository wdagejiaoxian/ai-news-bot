<template>
  <div class="cluster-chart" ref="chartRef"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { ClusterTopic } from '@/types/vector'

// 注册 ECharts 组件
echarts.use([
  LineChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  CanvasRenderer,
])

const props = defineProps<{
  clusters: ClusterTopic[]
  days: number
}>()

const chartRef = ref<HTMLElement | null>(null)
let chartInstance: echarts.ECharts | null = null

const processChartData = () => {
  // 按日期分组
  const dateMap = new Map<string, { total: number; emerging: number; hotness: number }>()

  props.clusters.forEach(cluster => {
    const date = cluster.date.split('T')[0] // 取日期部分
    const existing = dateMap.get(date) || { total: 0, emerging: 0, hotness: 0 }
    existing.total += 1
    if (cluster.is_emerging) {
      existing.emerging += 1
    }
    existing.hotness += cluster.hotness
    dateMap.set(date, existing)
  })

  // 排序
  const sortedDates = Array.from(dateMap.keys()).sort()
  const dates = sortedDates.map(d => {
    const date = new Date(d)
    return `${date.getMonth() + 1}/${date.getDate()}`
  })
  const totalData = sortedDates.map(d => dateMap.get(d)?.total || 0)
  const emergingData = sortedDates.map(d => dateMap.get(d)?.emerging || 0)

  return { dates, totalData, emergingData }
}

const initChart = () => {
  if (!chartRef.value) return

  chartInstance = echarts.init(chartRef.value)
  updateChart()
}

const updateChart = () => {
  if (!chartInstance) return

  const { dates, totalData, emergingData } = processChartData()

  // 如果没有数据，显示空状态
  if (dates.length === 0) {
    chartInstance.setOption({
      title: {
        text: '聚类趋势',
        textStyle: {
          fontSize: 14,
          fontWeight: 'normal',
        },
      },
      graphic: {
        type: 'text',
        left: 'center',
        top: 'center',
        style: {
          text: '暂无趋势数据',
          fontSize: 14,
          fill: '#909399',
        },
      },
    })
    return
  }

  const option: echarts.EChartsCoreOption = {
    title: {
      text: '聚类趋势',
      textStyle: {
        fontSize: 14,
        fontWeight: 'normal',
      },
    },
    tooltip: {
      trigger: 'axis',
    },
    legend: {
      data: ['总聚类数', '新兴话题数'],
      bottom: 0,
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '10%',
      top: '15%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: dates,
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
    },
    series: [
      {
        name: '总聚类数',
        type: 'line',
        smooth: true,
        areaStyle: {
          opacity: 0.3,
        },
        data: totalData,
      },
      {
        name: '新兴话题数',
        type: 'line',
        smooth: true,
        areaStyle: {
          opacity: 0.3,
        },
        data: emergingData,
      },
    ],
  }

  chartInstance.setOption(option)
}

// 监听窗口大小变化
const handleResize = () => {
  chartInstance?.resize()
}

watch(
  () => props.clusters,
  () => {
    updateChart()
  },
  { deep: true }
)

onMounted(() => {
  initChart()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  chartInstance?.dispose()
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.cluster-chart {
  width: 100%;
  height: 300px;
  background: var(--color-bg-card);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 20px;
}

@media (max-width: 768px) {
  .cluster-chart {
    height: 200px;
    padding: 12px;
  }
}
</style>
