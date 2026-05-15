/// <reference types="vite/client" />

/* ========== 第三方模块类型声明 ========== */

/**
 * Element Plus 中文语言包
 * element-plus/dist/locale/zh-cn.mjs 没有内置类型声明，
 * 此处手动补充，避免 vue-tsc 报 missing declaration 错误。
 */
declare module 'element-plus/dist/locale/zh-cn.mjs' {
  import type { Language } from 'element-plus/es/locale'
  const zhCn: Language
  export default zhCn
}
