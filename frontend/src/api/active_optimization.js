import request from './request.js'

export function getActiveOptimizations(params) {
  return request.get('/active-optimizations', { params })
}

export function getActiveOptimization(id) {
  return request.get(`/active-optimizations/${id}`)
}

export function createActiveOptimization(data) {
  return request.post('/active-optimizations', data)
}

export function updateActiveOptimization(id, data) {
  return request.put(`/active-optimizations/${id}`, data)
}

export function deleteActiveOptimization(id) {
  return request.delete(`/active-optimizations/${id}`)
}

export function getActiveOptimizationStats() {
  return request.get('/active-optimizations/stats/summary')
}

// ─────────── 关联需求文号（一对多） ───────────
// PUT = 全量覆盖（主写入方式，幂等）；POST = 增量添加

export function listActiveOptReqLinks(optId) {
  return request.get(`/active-optimizations/${optId}/req-links`)
}

export function replaceActiveOptReqLinks(optId, data) {
  return request.put(`/active-optimizations/${optId}/req-links`, data)
}

export function addActiveOptReqLinks(optId, data) {
  return request.post(`/active-optimizations/${optId}/req-links`, data)
}

export function removeActiveOptReqLink(optId, linkId) {
  return request.delete(`/active-optimizations/${optId}/req-links/${linkId}`)
}
