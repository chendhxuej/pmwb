import request from './request'

export function listWorkReports(params) {
  return request({ url: '/work-reports', method: 'get', params })
}

export function getWorkReport(id) {
  return request({ url: `/work-reports/${id}`, method: 'get' })
}

export function createWorkReport(data) {
  return request({ url: '/work-reports', method: 'post', data })
}

export function updateWorkReport(id, data) {
  return request({ url: `/work-reports/${id}`, method: 'put', data })
}

export function deleteWorkReport(id) {
  return request({ url: `/work-reports/${id}`, method: 'delete' })
}

export function generateWorkReport(data) {
  // 周报生成同步调 LLM（Kimi 生成长篇约 30~90s），必须放宽超时，否则前端 30s 提前断开误报
  return request({ url: '/work-reports/generate', method: 'post', data, timeout: 120000 })
}

export function finalizeWorkReport(id) {
  return request({ url: `/work-reports/${id}/finalize`, method: 'post' })
}

export function sendWorkReport(id, data) {
  // 发送走统一邮件中心，网络操作可能偏慢，放宽超时避免误报
  return request({ url: `/work-reports/${id}/send`, method: 'post', data, timeout: 120000 })
}
