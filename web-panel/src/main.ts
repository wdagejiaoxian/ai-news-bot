import { createApp } from 'vue'
import { createPinia } from 'pinia'
// Element Plus CSS 已通过 unplugin-element-plus 按需引入，无需全量导入
// zhCn 中文语言包已在 App.vue 中导入并使用

import App from './App.vue'
import router from './router'

// 全局样式（按引入顺序：变量 → 覆盖 → 基础样式）
import './assets/styles/variables.css'
import './assets/styles/element-overrides.css'
import './assets/styles/main.css'

const app = createApp(App)

// Element Plus 语言包（由 vite 插件自动导入组件）
app.use(createPinia())
app.use(router)

app.mount('#app')
