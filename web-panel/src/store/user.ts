import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { request } from '@/api'

export interface UserInfo {
  id: number
  username: string
  role?: string
  is_active: boolean
  created_at?: string
}

export const useUserStore = defineStore('user', () => {
  const token = ref<string | null>(localStorage.getItem('access_token'))
  const refreshToken = ref<string | null>(localStorage.getItem('refresh_token'))
  const userInfo = ref<UserInfo | null>(null)
  
  const isLoggedIn = computed(() => !!token.value)
  
  // 登录
  async function login(username: string, password: string) {
    const data = await request.post('/auth/login', { username, password })
    token.value = data.access_token
    refreshToken.value = data.refresh_token
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    return data
  }

  // 登出
  function logout() {
    token.value = null
    refreshToken.value = null
    userInfo.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
  }
  
  // 获取用户信息
  async function fetchUserInfo() {
    try {
      const data = await request.get('/auth/me')
      userInfo.value = data
      return data
    } catch (error) {
      logout()
      throw error
    }
  }
  
  // 刷新Token
  async function refreshAccessToken() {
    if (!refreshToken.value) {
      throw new Error('No refresh token')
    }
    
    const data = await request.post('/auth/refresh', {
      refresh_token: refreshToken.value,
    })
    
    token.value = data.access_token
    refreshToken.value = data.refresh_token
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    
    return data
  }
  
  return {
    token,
    refreshToken,
    userInfo,
    isLoggedIn,
    login,
    logout,
    fetchUserInfo,
    refreshAccessToken,
  }
})
