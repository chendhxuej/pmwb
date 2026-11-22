import request from './request.js'

// PRD 需求分析：独立 /prd 前缀，避开 /requirements/{req_id} 通配。
// request.js 拦截器在 code===0 时已返回 data.data，此处禁二次解包。

export function getPrdMeta() {
  return request.get('/prd/meta')
}

export function getPrdKnowledgeStatus() {
  return request.get('/prd/knowledge-status')
}

// LLM 需求分析可能耗时 2-5 分钟（外网模型+长上下文），放宽到 300s
export function analyzePrd(reqId, payload) {
  return request.post(`/prd/analyze/${encodeURIComponent(reqId)}`, payload, { timeout: 300000 })
}

export function getPrdStatus(reqId) {
  return request.get(`/prd/status/${encodeURIComponent(reqId)}`)
}

export function getPrdSources(traceId) {
  return request.get(`/prd/sources/${encodeURIComponent(traceId)}`)
}

export function finalizePrd(traceId) {
  return request.post(`/prd/finalize/${encodeURIComponent(traceId)}`)
}

// 下载统一走 utils/download.js（带 JWT），禁裸 URL
export function getPrdDownloadUrl(traceId) {
  return `/api/v1/prd/download/${encodeURIComponent(traceId)}`
}
