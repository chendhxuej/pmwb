import request from './request.js'

export function getRequirements(params) {
  return request.get('/api/v1/requirements', { params })
}

export function getRequirement(reqId) {
  return request.get(`/api/v1/requirements/${reqId}`)
}

export function updateRequirement(reqId, data) {
  return request.put(`/api/v1/requirements/${reqId}`, data)
}

export function getRequirementStats() {
  return request.get('/api/v1/requirements/stats')
}

export function getRequirementSystems() {
  return request.get('/api/v1/requirements/meta/systems')
}
