import { defineStore } from 'pinia'
import { ref } from 'vue'
import { loginApi } from '@/api/auth'
import { loadStatusMeta } from '@/api/statusMeta'

const TOKEN_KEY = 'pmwb_token'
const USERNAME_KEY = 'pmwb_username'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem(TOKEN_KEY) || '')
  const username = ref(localStorage.getItem(USERNAME_KEY) || '')

  async function login(name, password) {
    const res = await loginApi(name, password)
    if (res.code !== 0) throw new Error(res.message || '登录失败')
    token.value = res.data.token
    username.value = res.data.username
    localStorage.setItem(TOKEN_KEY, token.value)
    localStorage.setItem(USERNAME_KEY, username.value)
    // 登录前应用启动时的状态注册表预加载会 401（无 token），登录成功后必须重拉，
    // 否则无 seed 兜底的域（如 meeting）下拉只显示原始枚举值
    loadStatusMeta(true).catch(() => {})
    return res.data
  }

  function logout() {
    token.value = ''
    username.value = ''
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USERNAME_KEY)
  }

  return { token, username, login, logout }
})
