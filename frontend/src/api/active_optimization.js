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
