import axios from 'axios'
import { ElMessage } from 'element-plus'

const request = axios.create({
  baseURL: '/api/v1',
  // 全局默认 120s：大模型（AI 生成/问查比算/AI总结）等请求较慢，避免被 30s 过早截断
  timeout: 120000,
})

request.interceptors.request.use(
  (config) => {
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

request.interceptors.response.use(
  (response) => {
    const data = response.data
    // 后端部分接口用 {code, message, data} 包装，部分直接返回数据
    if (data && typeof data.code === 'number') {
      if (data.code !== 0) {
        ElMessage.error(data.message || '请求失败')
        return Promise.reject(data)
      }
      return data.data
    }
    return data
  },
  (error) => {
    ElMessage.error(error.message || '网络错误')
    return Promise.reject(error)
  }
)

export default request
