import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    // Element Plus 按需自动导入（JS 组件 + CSS 样式）
    AutoImport({
      resolvers: [ElementPlusResolver()],
      imports: ['vue'],
    }),
    Components({
      resolvers: [ElementPlusResolver({ importStyle: 'css' })],
    }),
  ],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    // 启用CSS代码分割
    cssCodeSplit: true,
    // 分块策略
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (id.includes('node_modules')) {
            if (id.includes('vue') || id.includes('pinia') || id.includes('vue-router')) {
              return 'vue-vendor'
            }
            if (id.includes('echarts')) {
              return 'echarts'
            }
            if (id.includes('axios') || id.includes('dayjs') || id.includes('@vueuse')) {
              return 'utils'
            }
          }
        },
      },
    },
  },
})
