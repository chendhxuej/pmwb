import request from './request.js'

export function getRequirements(params) {
  return request.get('/requirements', { params })
}

export function getRequirement(reqId) {
  return request.get(`/requirements/${reqId}`)
}

export function updateRequirement(reqId, data) {
  return request.put(`/requirements/${reqId}`, data)
}

export function getRequirementStats() {
  return request.get('/requirements/stats')
}

export function getRequirementSystems() {
  return request.get('/requirements/meta/systems')
}

export function getEvaluations(reqId) {
  return request.get(`/requirements/${reqId}/evaluations`)
}

export function updateEvaluation(reqId, evalId, data) {
  return request.put(`/requirements/${reqId}/evaluations/${evalId}`, data)
}
