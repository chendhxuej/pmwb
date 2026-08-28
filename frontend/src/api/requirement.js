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
  return request.post(`/requirements/${reqId}/delivery/attachments/upload`, form)
}

export function deleteRequirementAttachment(reqId, filename) {
  return request.post(`/requirements/${reqId}/delivery/attachments/delete`, { filename })
}

export function uploadRequirementManual(reqId, file, note = '操作手册') {
  const form = new FormData()
  form.append('file', file)
  form.append('note', note)
  return request.post(`/requirements/${reqId}/delivery/upload-manual`, form)
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

export function getUserStoryStats() {
  return request.get('/user-stories/stats')
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

// ---- 环节时间日志（6 步工作流） ----
export function getStageLogs(reqId) {
  return request.get(`/requirements/${reqId}/stage-logs`)
}

export function updateStageLog(reqId, stage, data) {
  return request.put(`/requirements/${reqId}/stage-logs/${stage}`, data)
}

// ---- 开发事件记录（启动开发子页） ----
export function listDevEvents(reqId) {
  return request.get(`/requirements/${reqId}/dev-events`)
}

export function createDevEvent(reqId, data) {
  return request.post(`/requirements/${reqId}/dev-events`, data)
}

export function updateDevEvent(reqId, eventId, data) {
  return request.put(`/requirements/${reqId}/dev-events/${eventId}`, data)
}

export function deleteDevEvent(reqId, eventId) {
  return request.delete(`/requirements/${reqId}/dev-events/${eventId}`)
}

// ---- 操作手册（生产部署子页，按系统区分） ----
export function listManuals(reqId) {
  return request.get(`/requirements/${reqId}/manuals`)
}

export function uploadManual(reqId, file, systemName) {
  const form = new FormData()
  form.append('file', file)
  form.append('system_name', systemName)
  return request.post(`/requirements/${reqId}/manuals/upload`, form)
}

export function deleteManual(reqId, manualId) {
  return request.delete(`/requirements/${reqId}/manuals/${manualId}`)
}

export function downloadManualUrl(reqId, manualId) {
  return `/api/v1/requirements/${encodeURIComponent(reqId)}/manuals/${manualId}/download`
}

export function previewManualUrl(reqId, manualId) {
  return `/api/v1/requirements/${encodeURIComponent(reqId)}/manuals/${manualId}/preview`
}
