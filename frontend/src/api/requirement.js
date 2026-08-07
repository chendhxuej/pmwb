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

export function deleteRequirement(reqId) {
  return request.delete(`/requirements/${reqId}`)
}

export function getEvaluations(reqId) {
  return request.get(`/requirements/${reqId}/evaluations`)
}

export function updateEvaluation(reqId, evalId, data) {
  return request.put(`/requirements/${reqId}/evaluations/${evalId}`, data)
}

export function createEvaluation(reqId, data) {
  return request.post(`/requirements/${reqId}/evaluations`, data)
}

export function deleteEvaluation(reqId, evalId) {
  return request.delete(`/requirements/${reqId}/evaluations/${evalId}`)
}

// ---- 需求交付（附件文件夹 / 用户故事 / 分析说明书） ----
export function initRequirementFolder(reqId) {
  return request.post(`/requirements/${reqId}/delivery/init-folder`)
}

export function listRequirementAttachments(reqId) {
  return request.get(`/requirements/${reqId}/delivery/attachments`)
}

export function uploadRequirementAttachment(reqId, file) {
  const form = new FormData()
  form.append('file', file)
  return request.post(`/requirements/${reqId}/delivery/attachments/upload`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function deleteRequirementAttachment(reqId, filename) {
  return request.post(`/requirements/${reqId}/delivery/attachments/delete`, { filename })
}

export function generateUserStories(reqId, content, strategy = 'rules_v2') {
  // LLM 策略（kimi-k2.6 带 reasoning）响应较慢，单独放宽到 120s
  const timeout = strategy === 'llm' ? 120000 : 30000
  return request.post(`/requirements/${reqId}/delivery/generate-user-stories`, { content, strategy }, { timeout })
}

export function getLlmStatus() {
  return request.get('/requirements/delivery/llm-status')
}

export function getUserStories(reqId) {
  return request.get(`/requirements/${reqId}/delivery/stories`)
}

export function saveUserStories(reqId, stories) {
  return request.put(`/requirements/${reqId}/delivery/stories`, stories)
}

// 全局用户故事模糊查询（跨需求，默认全量、按创建时间倒序、分页）
export function searchUserStories(params = {}) {
  const { keyword = '', finalized = null, page = 1, pageSize = 20 } = params
  const query = { page, page_size: pageSize }
  if (keyword) query.keyword = keyword
  if (finalized !== null && finalized !== '' && finalized !== undefined) {
    query.finalized = finalized
  }
  return request.get('/user-stories/search', { params: query })
}

export function generateRequirementDoc(reqId, stories, clarification) {
  return request.post(`/requirements/${reqId}/delivery/generate-doc`, { stories, clarification })
}
