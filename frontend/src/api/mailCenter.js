import request from './request.js'

const BASE = '/mail-center'

// ── 健康检查 ──
export function getHealth() {
  return request.get(`${BASE}/health`)
}

// ── 邮件账号 ──
export function getAccounts(params) {
  return request.get(`${BASE}/accounts`, { params })
}
export function getAccount(id) {
  return request.get(`${BASE}/accounts/${id}`)
}
export function createAccount(data) {
  return request.post(`${BASE}/accounts`, data)
}
export function updateAccount(id, data) {
  return request.put(`${BASE}/accounts/${id}`, data)
}
export function deleteAccount(id) {
  return request.delete(`${BASE}/accounts/${id}`)
}
export function setDefaultAccount(id) {
  return request.post(`${BASE}/accounts/${id}/set-default`)
}
export function testAccount(id) {
  return request.post(`${BASE}/accounts/${id}/test`)
}

// ── 通讯录 ──
export function getContacts(params) {
  return request.get(`${BASE}/contacts`, { params })
}
export function createContact(data) {
  return request.post(`${BASE}/contacts`, data)
}
export function updateContact(id, data) {
  return request.put(`${BASE}/contacts/${id}`, data)
}
export function deleteContact(id) {
  return request.delete(`${BASE}/contacts/${id}`)
}

// ── 联系人分组 ──
export function getContactGroups() {
  return request.get(`${BASE}/contact-groups`)
}
export function createContactGroup(data) {
  return request.post(`${BASE}/contact-groups`, data)
}
export function updateContactGroup(id, data) {
  return request.put(`${BASE}/contact-groups/${id}`, data)
}
export function deleteContactGroup(id) {
  return request.delete(`${BASE}/contact-groups/${id}`)
}

// ── 邮件模板 ──
export function getTemplates(params) {
  return request.get(`${BASE}/templates`, { params })
}
export function getTemplate(id) {
  return request.get(`${BASE}/templates/${id}`)
}
export function createTemplate(data) {
  return request.post(`${BASE}/templates`, data)
}
export function updateTemplate(id, data) {
  return request.put(`${BASE}/templates/${id}`, data)
}
export function deleteTemplate(id) {
  return request.delete(`${BASE}/templates/${id}`)
}
export function renderTemplate(id, data) {
  return request.post(`${BASE}/templates/${id}/render`, data)
}

// ── 发送日志 ──
export function getLogs(params) {
  return request.get(`${BASE}/logs`, { params })
}
export function getMergedLogs(params) {
  return request.get(`${BASE}/logs/merged`, { params })
}
export function getLog(id) {
  return request.get(`${BASE}/logs/${id}`)
}

// ── 统计概览 ──
export function getStats() {
  return request.get(`${BASE}/stats`)
}
