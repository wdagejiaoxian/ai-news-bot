import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/pages/login/index.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/',
    component: () => import('@/components/layout/index.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        redirect: '/dashboard',
      },
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/pages/dashboard/index.vue'),
        meta: { title: '数据看板', icon: 'DataBoard' },
      },
      {
        path: 'articles',
        name: 'Articles',
        component: () => import('@/pages/articles/index.vue'),
        meta: { title: '文章管理', icon: 'Document' },
      },
      {
        path: 'articles/:id',
        name: 'ArticleDetail',
        component: () => import('@/pages/articles/detail.vue'),
        meta: { title: '文章详情', hidden: true },
      },
      {
        path: 'github',
        name: 'GitHub',
        component: () => import('@/pages/github/index.vue'),
        meta: { title: 'GitHub项目', icon: 'Star' },
      },
      {
        path: 'rss',
        name: 'RSS',
        component: () => import('@/pages/rss/index.vue'),
        meta: { title: 'RSS源管理', icon: 'Connection' },
      },
      {
        path: 'rsshub-help',
        name: 'RSSHubHelp',
        component: () => import('@/pages/rsshub-help/index.vue'),
        meta: { title: 'RSSHub 帮助', icon: 'QuestionFilled' },
      },
      {
        path: 'user-llm-config',
        name: 'UserLLMConfig',
        component: () => import('@/pages/user-llm-config/index.vue'),
        meta: { title: '我的LLM', icon: 'Cpu' },
      },
      {
        path: 'webhook-config',
        name: 'WebhookConfig',
        component: () => import('@/pages/webhook-config/index.vue'),
        meta: { title: 'Webhook配置', icon: 'Bell' },
      },
      // 系统管理路由
      {
        path: 'scheduler',
        name: 'Scheduler',
        component: () => import('@/pages/scheduler/index.vue'),
        meta: { title: '定时任务', icon: 'Timer' },
      },
      {
        path: 'logs',
        name: 'Logs',
        component: () => import('@/pages/logs/index.vue'),
        meta: { title: '操作日志', icon: 'DocumentCopy' },
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('@/pages/settings/index.vue'),
        meta: { title: '系统设置', icon: 'Setting' },
      },
      {
        path: 'system-settings',
        name: 'SystemSettings',
        component: () => import('@/pages/settings/system-settings.vue'),
        meta: { title: '系统参数配置', icon: 'Setting', requiresAuth: true },
      },
      // 向量服务路由
      {
        path: 'vector/models',
        name: 'EmbeddingModels',
        component: () => import('@/pages/vector/EmbeddingModels.vue'),
        meta: { title: 'Embedding 模型', icon: 'Cpu' },
      },
      {
        path: 'vector/db',
        name: 'VectorDBConfig',
        component: () => import('@/pages/vector/VectorDBConfig.vue'),
        meta: { title: '向量库配置', icon: 'Connection' },
      },
      {
        path: 'clusters',
        name: 'Clusters',
        component: () => import('@/pages/clusters/index.vue'),
        meta: { title: '主题聚类', icon: 'TrendCharts' },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由守卫
router.beforeEach(async (to, _from, next) => {
  const token = localStorage.getItem('access_token')
  
  // 未登录且需要认证 → 跳转登录
  if (to.meta.requiresAuth !== false && !token) {
    next('/login')
    return
  }
  
  // 已登录访问登录页 → 跳转首页
  if (token && to.path === '/login') {
    next('/dashboard')
    return
  }
  
  next()
})

export default router
