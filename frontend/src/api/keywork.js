import request from './request.js'

// 分类映射（与后端 KeyWorkCategory 枚举一致）
export const CATEGORY_MAP = {
  hq_pilot: { label: '总部试点', tag: 'blue' },
  annual_task: { label: '年度任务', tag: 'green' },
  special_topic: { label: '专题工作', tag: 'amber' },
}

// 状态映射
export const STATUS_MAP = {
  planning: { label: '规划中', tag: 'gray' },
  in_progress: { label: '进行中', tag: 'blue' },
  completed: { label: '已完成', tag: 'green' },
  paused: { label: '已暂停', tag: 'amber' },
  cancelled: { label: '已取消', tag: 'red' },
}

// 优先级映射
export const PRIORITY_MAP = {
  P0: { label: 'P0', tag: 'red' },
  P1: { label: 'P1', tag: 'amber' },
  P2: { label: 'P2', tag: 'blue' },
  P3: { label: 'P3', tag: 'gray' },
}

// 里程碑/计划/待办 状态
export const MS_STATUS_MAP = {
  pending: { label: '未开始', tag: 'gray' },
  in_progress: { label: '进行中', tag: 'blue' },
  done: { label: '已完成', tag: 'green' },
  delayed: { label: '已延期', tag: 'red' },
}

export const TASK_STATUS_MAP = {
  todo: { label: '待办', tag: 'gray' },
  in_progress: { label: '进行中', tag: 'blue' },
  done: { label: '已完成', tag: 'green' },
  cancelled: { label: '已取消', tag: 'red' },
}

// ── 主 CRUD ──
export function listKeyWorks(params) {
  return request.get('/key-works', { params })
}

export function getKeyWorkStats() {
  return request.get('/key-works/stats')
}

export function getKeyWork(id) {
  return request.get(`/key-works/${id}`)
}

export function createKeyWork(data) {
  return request.post('/key-works', data)
}

export function updateKeyWork(id, data) {
  return request.put(`/key-works/${id}`, data)
}

export function deleteKeyWork(id) {
  return request.delete(`/key-works/${id}`)
}

// ── 进展日志 ──
export function addProgress(id, data) {
  return request.post(`/key-works/${id}/progress`, data)
}

export function deleteProgress(id, pid) {
  return request.delete(`/key-works/${id}/progress/${pid}`)
}

// ── 成员待办 ──
export function addMemberTask(id, data) {
  return request.post(`/key-works/${id}/member-tasks`, data)
}

export function updateMemberTask(id, tid, data) {
  return request.put(`/key-works/${id}/member-tasks/${tid}`, data)
}

export function deleteMemberTask(id, tid) {
  return request.delete(`/key-works/${id}/member-tasks/${tid}`)
}

// ── 里程碑 ──
export function addMilestone(id, data) {
  return request.post(`/key-works/${id}/milestones`, data)
}

export function updateMilestone(id, mid, data) {
  return request.put(`/key-works/${id}/milestones/${mid}`, data)
}

export function deleteMilestone(id, mid) {
  return request.delete(`/key-works/${id}/milestones/${mid}`)
}

// ── 团队成员 ──
export function addMember(id, data) {
  return request.post(`/key-works/${id}/members`, data)
}

export function deleteMember(id, mid) {
  return request.delete(`/key-works/${id}/members/${mid}`)
}

// ── 月度计划 ──
export function addMonthlyPlan(id, data) {
  return request.post(`/key-works/${id}/monthly-plans`, data)
}

export function deleteMonthlyPlan(id, pid) {
  return request.delete(`/key-works/${id}/monthly-plans/${pid}`)
}

// ── 周计划 ──
export function addWeeklyPlan(id, data) {
  return request.post(`/key-works/${id}/weekly-plans`, data)
}

export function deleteWeeklyPlan(id, pid) {
  return request.delete(`/key-works/${id}/weekly-plans/${pid}`)
}

// ── 交付物 ──
export function uploadDeliverable(id, file) {
  const form = new FormData()
  form.append('file', file)
  return request.post(`/key-works/${id}/deliverables/upload`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function listDeliverables(id) {
  return request.get(`/key-works/${id}/deliverables`)
}

export function downloadDeliverable(id, did) {
  return request.get(`/key-works/${id}/deliverables/${did}/download`, {
    responseType: 'blob',
  })
}

export function deleteDeliverable(id, did) {
  return request.delete(`/key-works/${id}/deliverables/${did}`)
}
