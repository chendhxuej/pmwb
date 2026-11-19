import request from './request.js'

// ── 排版管理（PB 批次，2026-11-19 pb-1 起）────────────────────
// request.js 已解 {code,message,data} 包络，调用方直接用 r.items / r.plan，
// 禁止二次解包（r.data?.data 会静默变 {}）。

// 枚举 / 倒排偏移 / 例外原因闭集 / 系统字典（唯一来源）
export function getPaibanMeta() {
  return request.get('/paiban/meta')
}

// 系统 → 版本计划回落预览：专属 / 统一默认 / 待补版本计划
export function resolveVersionPlan(system) {
  return request.get('/paiban/resolve', { params: { system } })
}

// 登记页实时预览派生截止（公式只在后端 constants/paiban.py，前端不另算）
export function previewDeadlines(payload) {
  return request.post('/paiban/deadlines/preview', payload)
}

// 版本计划列表（含派生四环节截止与准入判定时点）
export function listVersionPlans(params) {
  return request.get('/paiban/versions', { params })
}

// 计划详情：派生截止 + 变更日志 + 顺延目标版本
export function getVersionPlan(id) {
  return request.get(`/paiban/versions/${encodeURIComponent(id)}`)
}

// 登记 / 改期（改期逐字段留痕，派生截止自动重算）
export function createVersionPlan(payload) {
  return request.post('/paiban/versions', payload)
}

export function updateVersionPlan(id, payload) {
  return request.patch(`/paiban/versions/${encodeURIComponent(id)}`, payload)
}

// ── pb-2 候选池 / 纳入 ──────────────────────────────────────────
export function listCandidates(params) {
  return request.get('/paiban/candidates', { params })
}
export function includeCandidates(payload) {
  return request.post('/paiban/candidates/include', payload)
}
export function inlineInclude(payload) {
  return request.post('/paiban/tracks/inline-include', payload)
}
export function syncTracks(payload) {
  return request.post('/paiban/tracks/sync', payload)
}

// ── pb-3/4 跟踪 / 团队 ─────────────────────────────────────────
export function listPbTracks(params) {
  return request.get('/paiban/tracks', { params })
}
export function getTrackTimeline(id) {
  return request.get(`/paiban/tracks/${encodeURIComponent(id)}/timeline`)
}
export function setTrackResult(id, payload) {
  return request.post(`/paiban/tracks/${encodeURIComponent(id)}/result`, payload)
}
export function manualHandle(id, payload) {
  return request.post(`/paiban/tracks/${encodeURIComponent(id)}/manual`, payload)
}
export function removeTrack(id, payload) {
  return request.post(`/paiban/tracks/${encodeURIComponent(id)}/remove`, payload)
}
export function setTeamStage(id, payload) {
  return request.post(`/paiban/teams/${encodeURIComponent(id)}/stage`, payload)
}
export function batchSetTeamStage(items, operator = '页面') {
  return request.post('/paiban/teams/stage/batch', { items, operator })
}
export function teamMatrix(params) {
  return request.get('/paiban/team-matrix', { params })
}
export function simulateAdmission(params) {
  return request.post('/paiban/admission/simulate', null, { params })
}

// ── pb-5 风险 / pb-6 督办 ───────────────────────────────────────
export function listPbRisks(params) {
  return request.get('/paiban/risks', { params })
}
export function createPbRisk(trackId, payload) {
  return request.post(`/paiban/tracks/${encodeURIComponent(trackId)}/risks`, payload)
}
export function resolvePbRisk(id, payload) {
  return request.post(`/paiban/risks/${encodeURIComponent(id)}/resolve`, payload)
}
export function previewSupervise(payload) {
  return request.post('/paiban/supervise/preview', payload)
}
export function sendSupervise(payload) {
  return request.post('/paiban/supervise/send', payload)
}
export function listSuperviseBatches(params) {
  return request.get('/paiban/supervise/batches', { params })
}
export function getSuperviseBatch(no) {
  return request.get(`/paiban/supervise/batches/${encodeURIComponent(no)}`)
}

// ── pb-7 反馈 / pb-8 概览 ───────────────────────────────────────
export function submitPbFeedback(payload) {
  return request.post('/paiban/feedback/submit', payload)
}
export function batchPbFeedback(payload) {
  return request.post('/paiban/feedback/batch', payload)
}
export function pullMailFeedback(payload) {
  return request.post('/paiban/feedback/mail/pull', payload)
}
export function listPendingFeedback(params) {
  return request.get('/paiban/feedback/pending', { params })
}
export function reviewPbFeedback(id, payload) {
  return request.post(`/paiban/feedback/${encodeURIComponent(id)}/review`, payload)
}
export function rollbackPbFeedback(id, payload) {
  return request.post(`/paiban/feedback/${encodeURIComponent(id)}/rollback`, payload)
}
export function getPbOverview(planId) {
  return request.get('/paiban/overview', { params: { plan_id: planId } })
}
export function listMissingPlans() {
  return request.get('/paiban/tracks/missing-plans')
}
