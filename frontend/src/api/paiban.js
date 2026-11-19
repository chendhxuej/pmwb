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
