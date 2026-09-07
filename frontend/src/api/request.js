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
    // 关键修复：必须透出后端返回的真实错误文案，而非仅显示 axios 的
    // 通用 "Request failed with status code 4xx"，否则业务校验（如
    // "分类编码已存在"）对用户完全不可见，看起来像无解的 bug。
    const res = error.response
    let msg = '网络错误'
    if (res) {
      const data = res.data || {}
      const detail = data.detail
      if (typeof detail === 'string') {
        msg = detail
      } else if (Array.isArray(detail)) {
        // Pydantic 校验错误：detail 形如 [{loc, msg, type}, ...]
        msg = detail
          .map((d) => (d && d.msg ? d.msg : JSON.stringify(d)))
          .join('；')
      } else if (data.message) {
        msg = data.message
      } else {
        msg = `请求失败（HTTP ${res.status}）`
      }
    } else if (error.message) {
      msg = error.message
    }
    ElMessage.error(msg)
    return Promise.reject(error)
  }
)

export default request
