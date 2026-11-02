import axios from 'axios'

// 登录鉴权独立于 request 实例（mb-3）：
// 401 需要在路由守卫里静默处理并跳登录页，
// 不能走 request.js 的全局 ElMessage（避免守卫阶段弹错）。
const authHttp = axios.create({ baseURL: '/api/v1', timeout: 15000 })

function authHeader() {
  const token = localStorage.getItem('pmwb_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export function loginApi(username, password) {
  return authHttp
    .post('/auth/login', { username, password })
    .then((r) => r.data)
}

// 回显当前登录用户：后端 AUTH_REQUIRED=false 时返回 code 0 + 空 username（本地免登录直通）
export function fetchMe() {
  return authHttp
    .get('/auth/me', { headers: authHeader() })
    .then((r) => r.data)
}
