<template>
  <div class="dashboard">
    <!-- 配置完成度提示 -->
    <el-alert
      v-if="missingConfigs.length > 0"
      :title="`您还有 ${missingConfigs.length} 项配置未完成：${missingConfigs.join('、')}。完成配置后才能正常使用推送功能。`"
      type="warning"
      :closable="false"
      class="config-alert"
    />

    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stat-cards">
      <el-col :xs="12" :sm="6">
        <div class="stat-card stat-card--blue">
          <template v-if="statsLoading">
            <el-skeleton animated class="stat-skeleton">
              <template #template>
                <div class="stat-skeleton__icon"></div>
                <div class="stat-skeleton__content">
                  <el-skeleton-item variant="h3" style="width: 50%" />
                  <el-skeleton-item variant="text" style="width: 30%" />
                </div>
              </template>
            </el-skeleton>
          </template>
          <template v-else>
            <div class="stat-card__icon">
              <el-icon :size="22"><Document /></el-icon>
            </div>
            <div class="stat-card__content">
              <div class="stat-card__value">{{ stats.my_articles }}</div>
              <div class="stat-card__label">我的文章</div>
            </div>
          </template>
        </div>
      </el-col>

      <el-col :xs="12" :sm="6">
        <div class="stat-card stat-card--green">
          <template v-if="statsLoading">
            <el-skeleton animated class="stat-skeleton">
              <template #template>
                <div class="stat-skeleton__icon"></div>
                <div class="stat-skeleton__content">
                  <el-skeleton-item variant="h3" style="width: 50%" />
                  <el-skeleton-item variant="text" style="width: 30%" />
                </div>
              </template>
            </el-skeleton>
          </template>
          <template v-else>
            <div class="stat-card__icon">
              <el-icon :size="22"><Star /></el-icon>
            </div>
            <div class="stat-card__content">
              <div class="stat-card__value">{{ stats.github_repos }}</div>
              <div class="stat-card__label">GitHub项目</div>
            </div>
          </template>
        </div>
      </el-col>

      <el-col :xs="12" :sm="6">
        <div class="stat-card stat-card--orange">
          <template v-if="statsLoading">
            <el-skeleton animated class="stat-skeleton">
              <template #template>
                <div class="stat-skeleton__icon"></div>
                <div class="stat-skeleton__content">
                  <el-skeleton-item variant="h3" style="width: 50%" />
                  <el-skeleton-item variant="text" style="width: 30%" />
                </div>
              </template>
            </el-skeleton>
          </template>
          <template v-else>
            <div class="stat-card__icon">
              <el-icon :size="22"><Connection /></el-icon>
            </div>
            <div class="stat-card__content">
              <div class="stat-card__value">{{ stats.my_rss_sources }}</div>
              <div class="stat-card__label">我的RSS源</div>
            </div>
          </template>
        </div>
      </el-col>

      <el-col :xs="12" :sm="6">
        <div class="stat-card stat-card--red">
          <template v-if="statsLoading">
            <el-skeleton animated class="stat-skeleton">
              <template #template>
                <div class="stat-skeleton__icon"></div>
                <div class="stat-skeleton__content">
                  <el-skeleton-item variant="h3" style="width: 50%" />
                  <el-skeleton-item variant="text" style="width: 30%" />
                </div>
              </template>
            </el-skeleton>
          </template>
          <template v-else>
            <div class="stat-card__icon">
              <el-icon :size="22"><Bell /></el-icon>
            </div>
            <div class="stat-card__content">
              <div class="stat-card__value">{{ stats.articles }}</div>
              <div class="stat-card__label">总文章数</div>
            </div>
          </template>
        </div>
      </el-col>
    </el-row>

    <!-- 配置快捷入口 -->
    <el-card shadow="hover" class="config-card">
      <template #header>
        <div class="section-header">
          <span class="section-title">快捷配置</span>
        </div>
      </template>
      <el-row :gutter="16">
        <el-col :xs="24" :sm="8">
          <div class="config-item" @click="$router.push('/user-llm-config')">
            <div class="config-item__icon config-item__icon--blue">
              <el-icon :size="24"><Cpu /></el-icon>
            </div>
            <div class="config-item__info">
              <div class="config-item__title">我的LLM配置</div>
              <div class="config-item__desc">配置AI模型</div>
            </div>
            <el-icon class="config-item__arrow"><ArrowRight /></el-icon>
          </div>
        </el-col>
        <el-col :xs="24" :sm="8">
          <div class="config-item" @click="$router.push('/webhook-config')">
            <div class="config-item__icon config-item__icon--green">
              <el-icon :size="24"><Bell /></el-icon>
            </div>
            <div class="config-item__info">
              <div class="config-item__title">Webhook配置</div>
              <div class="config-item__desc">配置推送地址</div>
            </div>
            <el-icon class="config-item__arrow"><ArrowRight /></el-icon>
          </div>
        </el-col>
        <el-col :xs="24" :sm="8">
          <div class="config-item" @click="$router.push('/rss')">
            <div class="config-item__icon config-item__icon--orange">
              <el-icon :size="24"><Connection /></el-icon>
            </div>
            <div class="config-item__info">
              <div class="config-item__title">RSS源管理</div>
              <div class="config-item__desc">管理订阅源</div>
            </div>
            <el-icon class="config-item__arrow"><ArrowRight /></el-icon>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 图表区域 -->
    <el-row :gutter="20" class="charts-row">
      <!-- RSS源分布饼图 -->
      <el-col :xs="24" :sm="12" :lg="8">
        <el-card shadow="hover" class="chart-card" v-loading="chartLoading">
          <template #header>
            <div class="card-header">
              <span class="section-title">文章RSS源分布</span>
            </div>
          </template>
          <div class="chart-container" v-if="rssSourceData.length > 0">
            <v-chart :option="rssSourceOption" autoresize />
          </div>
          <div v-else class="chart-empty">
            <el-icon :size="32"><Document /></el-icon>
            <span>暂无数据</span>
          </div>
        </el-card>
      </el-col>

      <!-- 推送平台分布饼图 -->
      <el-col :xs="24" :sm="12" :lg="8">
        <el-card shadow="hover" class="chart-card">
          <template #header>
            <div class="card-header">
              <span class="section-title">推送平台分布（近30天）</span>
            </div>
          </template>
          <div class="chart-container" v-if="pushPlatformData.length > 0">
            <v-chart :option="pushPlatformOption" autoresize />
          </div>
          <div v-else class="chart-empty">
            <el-icon :size="32"><Bell /></el-icon>
            <span>暂无推送数据</span>
          </div>
        </el-card>
      </el-col>

      <!-- GitHub语言分布饼图 -->
      <el-col :xs="24" :sm="12" :lg="8">
        <el-card shadow="hover" class="chart-card" v-loading="chartLoading">
          <template #header>
            <div class="card-header">
              <span class="section-title">GitHub语言分布</span>
            </div>
          </template>
          <div class="chart-container" v-if="languageData.length > 0">
            <v-chart :option="languageOption" autoresize />
          </div>
          <div v-else class="chart-empty">
            <el-icon :size="32"><Star /></el-icon>
            <span>暂无数据</span>
          </div>
        </el-card>
      </el-col>

      <!-- 统计概览 -->
      <el-col :xs="24" :lg="8">
        <el-card shadow="hover" class="chart-card overview-card" v-loading="chartLoading">
          <template #header>
            <div class="card-header">
              <span class="section-title">内容统计概览</span>
            </div>
          </template>
          <div class="overview-content">
            <div class="overview-item">
              <div class="overview-label">文章总数</div>
              <div class="overview-value overview-value--primary">{{ stats.articles }}</div>
            </div>
            <div class="overview-item">
              <div class="overview-label">GitHub项目</div>
              <div class="overview-value overview-value--success">{{ stats.github_repos }}</div>
            </div>
            <div class="overview-item">
              <div class="overview-label">RSS订阅源</div>
              <div class="overview-value overview-value--warning">{{ stats.my_rss_sources }}</div>
            </div>
            <div class="overview-item">
              <div class="overview-label">活跃Webhook</div>
              <div class="overview-value overview-value--danger">{{ stats.active_webhook_count }}</div>
            </div>
            <div class="overview-item">
              <div class="overview-label">推送成功率</div>
              <div class="overview-value" :class="pushStats.success_rate >= 90 ? 'overview-value--success' : 'overview-value--danger'">
                {{ pushStats.success_rate }}%
              </div>
            </div>
            <div class="overview-item">
              <div class="overview-label">今日推送</div>
              <div class="overview-value overview-value--primary">{{ pushStats.today }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 趋势图 -->
    <el-row :gutter="20" class="charts-row">
      <el-col :span="24">
        <el-card shadow="hover" class="chart-card trend-card" v-loading="chartLoading">
          <template #header>
            <div class="card-header">
              <span class="section-title">内容趋势（近30天）</span>
            </div>
          </template>
          <div class="chart-container chart-container--tall" v-if="trendData.dates.length > 0">
            <v-chart :option="trendOption" autoresize />
          </div>
          <div v-else class="chart-empty">
            <el-icon :size="32"><Connection /></el-icon>
            <span>暂无趋势数据</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 热点话题 -->
    <div class="hot-topics-section">
      <div class="section-header">
        <h3>🔥 热点话题</h3>
        <el-button text @click="router.push('/clusters')">查看全部</el-button>
      </div>

      <div v-if="topicsLoading" class="topics-loading">
        <el-skeleton animated :rows="1" />
      </div>

      <el-empty v-else-if="hotTopics.length === 0" description="暂无热点话题" :image-size="60" />

      <el-row v-else :gutter="16">
        <el-col :xs="24" :sm="8" v-for="topic in hotTopics" :key="topic.id">
          <div
            class="topic-card"
            :class="{ 'topic-card--emerging': topic.is_emerging }"
            @click="router.push('/clusters')"
          >
            <div class="topic-keywords">
              <el-tag
                v-for="keyword in topic.keywords.slice(0, 3)"
                :key="keyword"
                size="small"
                :type="topic.is_emerging ? 'warning' : ''"
              >
                {{ keyword }}
              </el-tag>
            </div>
            <div class="topic-meta">
              <span>{{ topic.article_count }} 篇文章</span>
              <span class="hotness">热度 {{ topic.hotness.toFixed(1) }}</span>
              <el-tag v-if="topic.is_emerging" type="warning" size="small" effect="dark">
                新兴
              </el-tag>
            </div>
          </div>
        </el-col>
      </el-row>
    </div>

    <!-- 最新内容 -->
    <el-row :gutter="20" class="content-row">
      <el-col :xs="24" :lg="12">
        <el-card shadow="hover" class="content-card">
          <template #header>
            <div class="card-header">
              <span class="section-title">最新文章</span>
              <el-button type="primary" link @click="$router.push('/articles')">查看更多</el-button>
            </div>
          </template>
          <el-table :data="recentArticles" max-height="300" class="dashboard-table">
            <el-table-column prop="title" label="标题" min-width="150">
              <template #default="{ row }">
                <span class="article-title">{{ row.title }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="source_name" label="来源" width="120" align="center" />
            <el-table-column prop="score" label="评分" width="100" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="getScoreType(row.score)" class="score-tag">
                  {{ row.score?.toFixed(1) || '-' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="12">
        <el-card shadow="hover" class="content-card">
          <template #header>
            <div class="card-header">
              <span class="section-title">GitHub热门</span>
              <el-button type="primary" link @click="$router.push('/github')">查看更多</el-button>
            </div>
          </template>
          <el-table :data="recentRepos" max-height="300" class="dashboard-table">
            <el-table-column prop="full_name" label="项目" min-width="120">
              <template #default="{ row }">
                <span class="repo-name">{{ row.full_name }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="language" label="语言" width="100" align="center">
              <template #default="{ row }">
                <span v-if="row.language" class="language-tag">{{ row.language }}</span>
                <span v-else class="text-muted">-</span>
              </template>
            </el-table-column>
            <el-table-column prop="stars" label="Stars" width="110" align="center">
              <template #default="{ row }">
                <span class="stars-count">⭐ {{ row.stars }}</span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart, LineChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
} from 'echarts/components'
import VChart from 'vue-echarts'
import { request } from '@/api'
import { useUserStore } from '@/store'
import { getClusterStats } from '@/api/vector'
import { getPushLogsStats } from '@/api/push_logs'
import type { ClusterTopic } from '@/types/vector'
import {
  Document,
  Star,
  Connection,
  Bell,
  Cpu,
  ArrowRight,
} from '@element-plus/icons-vue'

// 注册 ECharts 组件
use([
  CanvasRenderer,
  PieChart,
  LineChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
])

const userStore = useUserStore()
const router = useRouter()

// 热点话题
const hotTopics = ref<ClusterTopic[]>([])
const topicsLoading = ref(false)

const fetchHotTopics = async () => {
  topicsLoading.value = true
  try {
    const data = await getClusterStats(7)
    hotTopics.value = (data || []).slice(0, 3) // 只取 Top 3
  } catch (error) {
    console.error('获取热点话题失败:', error)
    hotTopics.value = []
  } finally {
    topicsLoading.value = false
  }
}

const stats = ref({
  articles: 0,
  github_repos: 0,
  my_articles: 0,
  my_rss_sources: 0,
  active_model_count: 0,
  active_webhook_count: 0,
  embedding_model_count: 0,
})

const pushStats = ref({
  total: 0,
  success_count: 0,
  fail_count: 0,
  success_rate: 0,
  today: 0,
  by_platform: {} as Record<string, number>,
})

const recentArticles = ref<Record<string, unknown>[]>([])
const recentRepos = ref<Record<string, unknown>[]>([])

// 图表数据
const chartLoading = ref(false)
const statsLoading = ref(true)
const rssSourceData = ref<{ name: string; value: number }[]>([])
const languageData = ref<{ name: string; value: number }[]>([])
const pushPlatformData = ref<{ name: string; value: number }[]>([])
const trendData = ref<{
  dates: string[]
  articles: number[]
  github_repos: number[]
  pushes: number[]
}>({
  dates: [],
  articles: [],
  github_repos: [],
  pushes: [],
})

// ECharts 主题颜色
const chartTheme = computed(() => {
  const isDark = document.documentElement.classList.contains('dark')
  return {
    textColor: isDark ? '#8e8e93' : '#45515e',
    borderColor: isDark ? '#2f3842' : '#e5e7eb',
    borderLight: isDark ? '#222930' : '#f2f3f5',
    bgCard: isDark ? '#222930' : '#ffffff',
    primary: '#6366f1',
    primaryLight: 'rgba(99, 102, 241, 0.3)',
    primaryFade: 'rgba(99, 102, 241, 0.05)',
    success: '#10b981',
    successLight: 'rgba(16, 185, 129, 0.3)',
    successFade: 'rgba(16, 185, 129, 0.05)',
    warning: '#f59e0b',
    warningLight: 'rgba(245, 158, 11, 0.3)',
    warningFade: 'rgba(245, 158, 11, 0.05)',
  }
})

// RSS源饼图配置
const rssSourceOption = computed(() => ({
  tooltip: {
    trigger: 'item',
    formatter: '{b}: {c} ({d}%)',
  },
  legend: {
    orient: 'vertical',
    right: 10,
    top: 'center',
    textStyle: {
      color: chartTheme.value.textColor,
      overflow: 'truncate',
      width: 80,
    },
  },
  series: [
    {
      name: 'RSS源分布',
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['35%', '50%'],
      avoidLabelOverlap: false,
      itemStyle: {
        borderRadius: 6,
        borderColor: chartTheme.value.bgCard,
        borderWidth: 2,
      },
      label: {
        show: false,
      },
      emphasis: {
        label: {
          show: true,
          fontSize: 14,
          fontWeight: 'bold',
        },
      },
      data: rssSourceData.value,
    },
  ],
}))

// GitHub语言饼图配置
const languageOption = computed(() => ({
  tooltip: {
    trigger: 'item',
    formatter: '{b}: {c} ({d}%)',
  },
  legend: {
    orient: 'vertical',
    right: 10,
    top: 'center',
    textStyle: {
      color: chartTheme.value.textColor,
    },
  },
  series: [
    {
      name: '语言分布',
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['35%', '50%'],
      avoidLabelOverlap: false,
      itemStyle: {
        borderRadius: 6,
        borderColor: chartTheme.value.bgCard,
        borderWidth: 2,
      },
      label: {
        show: false,
      },
      emphasis: {
        label: {
          show: true,
          fontSize: 14,
          fontWeight: 'bold',
        },
      },
      data: languageData.value,
    },
  ],
}))

// 推送平台饼图配置
const pushPlatformOption = computed(() => ({
  tooltip: {
    trigger: 'item',
    formatter: '{b}: {c} ({d}%)',
  },
  legend: {
    orient: 'vertical',
    right: 10,
    top: 'center',
    textStyle: {
      color: chartTheme.value.textColor,
      overflow: 'truncate',
      width: 80,
    },
  },
  series: [
    {
      name: '推送平台',
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['35%', '50%'],
      avoidLabelOverlap: false,
      itemStyle: {
        borderRadius: 6,
        borderColor: chartTheme.value.bgCard,
        borderWidth: 2,
      },
      label: {
        show: false,
      },
      emphasis: {
        label: {
          show: true,
          fontSize: 14,
          fontWeight: 'bold',
        },
      },
      data: pushPlatformData.value,
    },
  ],
}))

// 趋势折线图配置
const trendOption = computed(() => ({
  tooltip: {
    trigger: 'axis',
    axisPointer: {
      type: 'shadow',
    },
  },
  legend: {
    data: ['文章', 'GitHub', '推送'],
    bottom: 0,
    textStyle: {
      color: chartTheme.value.textColor,
    },
  },
  grid: {
    left: '3%',
    right: '4%',
    bottom: '15%',
    top: '10%',
    containLabel: true,
  },
  xAxis: {
    type: 'category',
    boundaryGap: false,
    data: trendData.value.dates,
    axisLabel: {
      color: chartTheme.value.textColor,
      fontSize: 11,
      rotate: 45,
    },
    axisLine: {
      lineStyle: {
        color: chartTheme.value.borderColor,
      },
    },
  },
  yAxis: {
    type: 'value',
    axisLabel: {
      color: chartTheme.value.textColor,
    },
    axisLine: {
      show: true,
      lineStyle: {
        color: chartTheme.value.borderColor,
      },
    },
    splitLine: {
      lineStyle: {
        color: chartTheme.value.borderLight,
      },
    },
  },
  series: [
    {
      name: '文章',
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      itemStyle: {
        color: chartTheme.value.primary,
      },
      lineStyle: {
        color: chartTheme.value.primary,
        width: 2,
      },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0,
          y: 0,
          x2: 0,
          y2: 1,
          colorStops: [
            { offset: 0, color: chartTheme.value.primaryLight },
            { offset: 1, color: chartTheme.value.primaryFade },
          ],
        },
      },
      data: trendData.value.articles,
    },
    {
      name: 'GitHub',
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      itemStyle: {
        color: chartTheme.value.success,
      },
      lineStyle: {
        color: chartTheme.value.success,
        width: 2,
      },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0,
          y: 0,
          x2: 0,
          y2: 1,
          colorStops: [
            { offset: 0, color: chartTheme.value.successLight },
            { offset: 1, color: chartTheme.value.successFade },
          ],
        },
      },
      data: trendData.value.github_repos,
    },
    {
      name: '推送',
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      itemStyle: {
        color: chartTheme.value.warning,
      },
      lineStyle: {
        color: chartTheme.value.warning,
        width: 2,
      },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0,
          y: 0,
          x2: 0,
          y2: 1,
          colorStops: [
            { offset: 0, color: chartTheme.value.warningLight },
            { offset: 1, color: chartTheme.value.warningFade },
          ],
        },
      },
      data: trendData.value.pushes,
    },
  ],
}))

const missingConfigs = computed(() => {
  const missing: string[] = []
  if (!userStore.userInfo) return missing
  if (stats.value.active_model_count === 0) missing.push('LLM模型')
  if (stats.value.active_webhook_count === 0) missing.push('Webhook')
  if (stats.value.my_rss_sources === 0) missing.push('RSS源')
  return missing
})

// Embedding模型配置状态（可选配置，单独管理）
const isEmbeddingConfigured = computed(() => {
  return stats.value.embedding_model_count > 0
})

function getScoreType(score: number | null): string {
  if (!score) return 'info'
  if (score >= 85) return 'success'
  if (score >= 65) return 'warning'
  return 'danger'
}

async function fetchDashboard() {
  statsLoading.value = true
  try {
    const data = await request.get('/stats/dashboard')
    stats.value = {
      articles: data.articles || 0,
      github_repos: data.github_repos || 0,
      my_articles: data.my_articles || 0,
      my_rss_sources: data.my_rss_sources || 0,
      active_model_count: data.active_model_count || 0,
      active_webhook_count: data.active_webhook_count || 0,
      embedding_model_count: data.embedding_model_count || 0,
    }
    recentArticles.value = data.recent_articles || []
    recentRepos.value = data.recent_repos || []
  } catch (error) {
    console.debug('获取Dashboard数据失败:', error)
    ElMessage.error('获取数据失败，请刷新页面重试')
  } finally {
    statsLoading.value = false
  }
}

async function fetchChartData() {
  chartLoading.value = true
  try {
    // 获取详细统计
    const detailedData = await request.get('/stats/detailed')

    // 转换RSS源数据
    if (detailedData.articles?.by_source) {
      rssSourceData.value = Object.entries(detailedData.articles.by_source).map(
        ([name, value]) => ({ name, value: value as number })
      )
    }

    // 转换语言数据
    if (detailedData.github_repos?.by_language) {
      languageData.value = Object.entries(detailedData.github_repos.by_language).map(
        ([name, value]) => ({ name, value: value as number })
      )
    }

    // 获取趋势数据
    const trendResult = await request.get('/stats/trends', { params: { days: 30 } })
    trendData.value = {
      dates: trendResult.dates || [],
      articles: trendResult.articles || [],
      github_repos: trendResult.github_repos || [],
      pushes: trendResult.pushes || [],
    }
  } catch (error) {
    console.debug('获取图表数据失败:', error)
    ElMessage.error('获取图表数据失败')
  } finally {
    chartLoading.value = false
  }
}

async function fetchPushStats() {
  try {
    const data = await getPushLogsStats({ days: 30 })
    pushStats.value = {
      total: data.total,
      success_count: data.success_count,
      fail_count: data.fail_count,
      success_rate: data.success_rate,
      today: data.today,
      by_platform: data.by_platform || {},
    }
    // 转换平台分布数据
    pushPlatformData.value = Object.entries(data.by_platform || {}).map(
      ([name, value]) => ({ name, value })
    )
  } catch (error) {
    console.debug('获取推送统计失败:', error)
  }
}

onMounted(async () => {
  // 并行加载所有数据
  await Promise.all([
    userStore.userInfo ? Promise.resolve() : userStore.fetchUserInfo().catch(() => {}),
    fetchDashboard(),
    fetchChartData(),
    fetchHotTopics(),
    fetchPushStats(),
  ])
})
</script>

<style scoped>
.dashboard {
  padding: 0;
}

/* ==================== 配置提示 ==================== */

.config-alert {
  margin-bottom: var(--spacing-lg);
  border-radius: var(--radius-lg);
}

/* ==================== 统计卡片 ==================== */

.stat-cards {
  margin-bottom: var(--spacing-lg);
}

.stat-card {
  position: relative;
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-lg);
  margin-bottom: var(--spacing-md);
  border-radius: var(--radius-2xl);
  background: var(--color-bg-card);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
  cursor: pointer;
  transition:
    transform var(--transition-duration-fast) var(--transition-timing),
    box-shadow var(--transition-duration-fast) var(--transition-timing);
  /* 微妙渐变背景 - 默认隐藏 */
  background-image: linear-gradient(
    135deg,
    rgba(99, 102, 241, 0.03) 0%,
    rgba(139, 92, 246, 0.03) 100%
  );
}

/* 光晕效果层 */
.stat-card::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  border-radius: inherit;
  opacity: 0;
  transition: opacity var(--transition-duration-normal) var(--transition-timing);
  pointer-events: none;
}

.stat-card--blue::after {
  background: radial-gradient(circle at 20% 80%, var(--color-primary-alpha-10) 0%, transparent 60%);
}

.stat-card--green::after {
  background: radial-gradient(circle at 20% 80%, var(--color-success-alpha-10) 0%, transparent 60%);
}

.stat-card--orange::after {
  background: radial-gradient(circle at 20% 80%, var(--color-warning-alpha-10) 0%, transparent 60%);
}

.stat-card--red::after {
  background: radial-gradient(circle at 20% 80%, var(--color-danger-alpha-10) 0%, transparent 60%);
}

.stat-card::before {
  content: '';
  position: absolute;
  top: 0;
  right: 0;
  width: 80px;
  height: 80px;
  border-radius: 50%;
  opacity: 0.1;
  transform: translate(30%, -30%);
  transition: transform var(--transition-duration-normal) var(--transition-timing);
}

.stat-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-brand);
  background-image: linear-gradient(
    135deg,
    rgba(99, 102, 241, 0.08) 0%,
    rgba(139, 92, 246, 0.08) 100%
  );
}

.stat-card:hover::after {
  opacity: 1;
}

.stat-card:hover::before {
  transform: translate(20%, -20%) scale(1.2);
}

.stat-card--blue::before {
  background: var(--color-primary);
}

.stat-card--green::before {
  background: var(--color-success);
}

.stat-card--orange::before {
  background: var(--color-warning);
}

.stat-card--red::before {
  background: var(--color-danger);
}

.stat-card__icon {
  width: 52px;
  height: 52px;
  border-radius: var(--radius-xl);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-inverse);
  flex-shrink: 0;
  transition: transform var(--transition-duration-fast) var(--transition-timing);
  position: relative;
  z-index: 1;
}

.stat-card:hover .stat-card__icon {
  transform: scale(1.08);
}

.stat-card--blue .stat-card__icon {
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-hover) 100%);
  box-shadow: 0 4px 12px var(--color-primary-alpha-20);
}

.stat-card--green .stat-card__icon {
  background: linear-gradient(135deg, var(--color-success) 0%, var(--color-green-lighter) 100%);
  box-shadow: 0 4px 12px var(--color-success-alpha-30);
}

.stat-card--orange .stat-card__icon {
  background: linear-gradient(135deg, var(--color-warning) 0%, var(--color-orange-lighter) 100%);
  box-shadow: 0 4px 12px var(--color-warning-alpha-30);
}

.stat-card--red .stat-card__icon {
  background: linear-gradient(135deg, var(--color-danger) 0%, var(--color-red-light) 100%);
  box-shadow: 0 4px 12px var(--color-danger-alpha-30);
}

.stat-card__content {
  flex: 1;
  min-width: 0;
  z-index: 1;
}

.stat-card__value {
  font-family: var(--font-family-display);
  font-size: var(--font-size-h1);
  font-weight: var(--font-weight-bold);
  color: var(--color-text-primary);
  line-height: 1.1;
  letter-spacing: -0.02em;
}

.stat-card__label {
  font-size: var(--font-size-small);
  color: var(--color-text-secondary);
  margin-top: var(--spacing-xs);
}

/* 统计卡片骨架屏 */
.stat-skeleton {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-lg);
  width: 100%;
}

.stat-skeleton__icon {
  width: 52px;
  height: 52px;
  border-radius: var(--radius-xl);
  background: var(--color-bg-content);
}

.stat-skeleton__content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

/* ==================== 配置卡片 ==================== */

.config-card {
  margin-bottom: var(--spacing-lg);
  border-radius: var(--radius-2xl);
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.section-title {
  font-family: var(--font-family-display);
  font-size: var(--font-size-h4);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}

/* ==================== 配置项 ==================== */

.config-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-md);
  margin-bottom: var(--spacing-sm);
  border-radius: var(--radius-xl);
  background: var(--color-bg-content);
  cursor: pointer;
  transition:
    background-color var(--transition-duration-fast) var(--transition-timing),
    transform var(--transition-duration-fast) var(--transition-timing);
}

.config-item:last-child {
  margin-bottom: 0;
}

.config-item:hover {
  background: var(--color-bg-card);
  transform: translateX(4px);
}

.config-item__icon {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-inverse);
  flex-shrink: 0;
}

.config-item__icon--blue {
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-hover) 100%);
}

.config-item__icon--green {
  background: linear-gradient(135deg, var(--color-success) 0%, var(--color-green-lighter) 100%);
}

.config-item__icon--orange {
  background: linear-gradient(135deg, var(--color-warning) 0%, var(--color-orange-lighter) 100%);
}

.config-item__info {
  flex: 1;
  min-width: 0;
}

.config-item__title {
  font-size: var(--font-size-body);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-primary);
}

.config-item__desc {
  font-size: var(--font-size-small);
  color: var(--color-text-muted);
  margin-top: 2px;
}

.config-item__arrow {
  font-size: 18px;
  color: var(--color-text-muted);
  transition: transform var(--transition-duration-fast) var(--transition-timing);
}

.config-item:hover .config-item__arrow {
  transform: translateX(4px);
  color: var(--color-primary);
}

/* ==================== 图表区域 ==================== */

.charts-row {
  margin-top: var(--spacing-lg);
}

.chart-card {
  margin-bottom: var(--spacing-lg);
  border-radius: var(--radius-2xl);
  transition: box-shadow var(--transition-duration-fast) var(--transition-timing);
}

.chart-card:hover {
  box-shadow: var(--shadow-brand);
}

.chart-container {
  height: 280px;
  width: 100%;
}

.chart-container--tall {
  height: 320px;
}

.chart-container :deep(.vue-echarts) {
  width: 100% !important;
  height: 100% !important;
}

.chart-empty {
  height: 200px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-sm);
  color: var(--color-text-muted);
}

.chart-empty .el-icon {
  font-size: 32px;
  opacity: 0.5;
}

/* 概览卡片 */
.overview-card .el-card__body {
  padding: var(--spacing-md);
}

.overview-content {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--spacing-md);
}

.overview-item {
  padding: var(--spacing-md);
  background: var(--color-bg-content);
  border-radius: var(--radius-lg);
  text-align: center;
}

.overview-label {
  font-size: var(--font-size-micro);
  color: var(--color-text-muted);
  margin-bottom: var(--spacing-xs);
}

.overview-value {
  font-family: var(--font-family-display);
  font-size: var(--font-size-h2);
  font-weight: var(--font-weight-bold);
  line-height: 1.2;
}

.overview-value--primary {
  color: var(--color-primary);
}

.overview-value--success {
  color: var(--color-success);
}

.overview-value--warning {
  color: var(--color-warning);
}

.overview-value--danger {
  color: var(--color-danger);
}

/* 趋势卡片 */
.trend-card .el-card__body {
  padding: var(--spacing-md) var(--spacing-lg);
}

/* ==================== 热点话题 ==================== */

.hot-topics-section {
  margin: var(--spacing-lg) 0;
  background: var(--color-bg-card);
  border-radius: 8px;
  padding: 20px;
  box-shadow: var(--shadow-sm);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.topics-loading {
  padding: 20px 0;
}

.topic-card {
  background: var(--color-bg-content);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 12px;
  cursor: pointer;
  transition: all 0.2s;
  margin-bottom: 12px;
}

.topic-card:hover {
  border-color: var(--color-primary);
  box-shadow: var(--shadow-md);
}

.topic-card--emerging {
  border-left: 3px solid var(--color-warning);
}

.topic-keywords {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.topic-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--color-text-muted);
}

.topic-meta .hotness {
  color: var(--color-warning);
}

@media (max-width: 768px) {
  .hot-topics-section {
    padding: 12px;
  }
}

/* ==================== 内容卡片 ==================== */

.content-row {
  margin-top: var(--spacing-lg);
}

.content-card {
  margin-bottom: var(--spacing-lg);
  border-radius: var(--radius-2xl);
  transition: box-shadow var(--transition-duration-fast) var(--transition-timing);
}

.content-card:hover {
  box-shadow: var(--shadow-brand);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* ==================== 表格样式优化 ==================== */

.dashboard-table {
  font-size: var(--font-size-small);
}

.dashboard-table .el-table__header th {
  font-weight: var(--font-weight-medium);
}

.article-title,
.repo-name {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
  color: var(--color-text-primary);
  transition: color var(--transition-duration-fast) var(--transition-timing);
}

.dashboard-table tr:hover .article-title,
.dashboard-table tr:hover .repo-name {
  color: var(--color-primary);
}

.language-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  background: var(--color-bg-content);
  color: var(--color-text-secondary);
  font-size: var(--font-size-micro);
  white-space: nowrap;
  overflow: visible;
  max-width: none;
}

.stars-count {
  color: var(--color-text-secondary);
  font-size: var(--font-size-small);
  white-space: normal;
  word-break: break-word;
  overflow: visible;
  max-width: none;
}

.text-muted {
  color: var(--color-text-muted);
}

.score-tag {
  max-width: 100%;
  overflow: visible;
  text-overflow: clip;
  white-space: nowrap;
}

/* ==================== 响应式 ==================== */

@media (max-width: 767px) {
  .stat-card {
    padding: var(--spacing-md);
    gap: var(--spacing-sm);
  }

  .stat-card__icon {
    width: 44px;
    height: 44px;
  }

  .stat-card__value {
    font-size: var(--font-size-h2);
  }

  .config-item {
    padding: var(--spacing-sm);
  }

  .config-item__icon {
    width: 40px;
    height: 40px;
  }

  .content-card {
    border-radius: var(--radius-lg);
  }

  .chart-container {
    height: 240px;
  }

  .chart-container--tall {
    height: 280px;
  }

  .overview-content {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 575px) {
  .stat-card {
    flex-direction: column;
    text-align: center;
    padding: var(--spacing-md);
  }

  .stat-card__content {
    width: 100%;
  }

  .chart-container {
    height: 220px;
  }
}
</style>
