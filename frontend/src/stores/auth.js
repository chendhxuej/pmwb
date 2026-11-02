import { defineStore } from 'pinia'
import { ref } from 'vue'
import { loginApi } from '@/api/auth'

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
